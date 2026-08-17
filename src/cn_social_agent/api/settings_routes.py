"""Workbench LLM settings + per-user preference memory."""

from __future__ import annotations

import os

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.api.prefs import merge_prefs
from cn_social_agent.llm import AgnesLLM, OllamaLLM
from cn_social_agent.llm.router import pick_default_fast, pick_default_strong


async def _agnes_models() -> list[str]:
    if not AgnesLLM.configured():
        return list(AgnesLLM.FALLBACK_CHAT_MODELS)
    try:
        ids = await AgnesLLM().list_chat_model_ids(limit=80)
        return ids or list(AgnesLLM.FALLBACK_CHAT_MODELS)
    except Exception:  # noqa: BLE001
        return list(AgnesLLM.FALLBACK_CHAT_MODELS)


async def _ollama_models() -> list[str]:
    ids = await OllamaLLM.list_model_ids(limit=40)
    if ids:
        return ids
    return ["gemma2:2b", "llama3.2", "qwen2.5"]


async def _insforge_provider(state) -> tuple[dict, str | None]:
    """Build InsForge provider entry; return (provider_dict, error_message)."""
    err: str | None = None
    models: list[str] = []
    default_model = "openai/gpt-4o-mini"
    configured = False
    if state.insforge is not None and getattr(state.insforge, "llm", None):
        llm = state.insforge.llm
        default_model = getattr(llm, "model", None) or default_model
        try:
            configured = await llm.available()
            if configured:
                models = await llm.list_model_ids(limit=80)
                if not models and default_model:
                    models = [default_model]
            else:
                err = "InsForge AI Gateway 不可用或未配置 OPENROUTER_API_KEY"
        except Exception as exc:  # noqa: BLE001
            err = str(exc)
            configured = False
    else:
        # Fall back to env hint when InsForge client missing
        configured = bool(
            os.getenv("INSFORGE_OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        )
        if not configured:
            err = "InsForge 未初始化"
    return (
        {
            "id": "insforge",
            "label": "InsForge / OpenRouter",
            "configured": configured,
            "models": models,
            "default_model": default_model if configured else "",
            "source": "insforge",
        },
        err,
    )


async def _maybe_restore_user_llm(state, user_id: str) -> None:
    """Align process LLM with the signed-in user's saved prefs (single-user workbench)."""
    try:
        prefs = await state.store.get_user_prefs(user_id)
    except Exception:  # noqa: BLE001
        return
    mode = (prefs.get("llm_mode") or "").strip().lower()
    model = (prefs.get("llm_model") or "").strip() or None
    if not mode:
        return
    current_model = ""
    if state.agent and hasattr(state.agent.llm, "model"):
        current_model = getattr(state.agent.llm, "model", "") or ""
    if mode == state.llm_mode and (not model or model == current_model):
        return
    try:
        await state.switch_llm(mode, model=model)
    except Exception as exc:  # noqa: BLE001
        print(f"[workbench] restore user llm failed ({exc})")


@require_user
async def get_llm_settings(request: web.Request) -> web.Response:
    state = get_state(request)
    user_id = request["user"]["id"]
    await _maybe_restore_user_llm(state, user_id)

    ollama_ok = await OllamaLLM.available()
    inf_provider, inf_err = await _insforge_provider(state)
    agnes_models = await _agnes_models() if AgnesLLM.configured() else list(
        AgnesLLM.FALLBACK_CHAT_MODELS
    )
    ollama_models = await _ollama_models() if ollama_ok else ["gemma2:2b", "llama3.2", "qwen2.5"]
    providers = [
        {
            "id": "agnes",
            "label": "Agnes",
            "configured": AgnesLLM.configured(),
            "models": agnes_models,
            "default_model": AgnesLLM.DEFAULT_MODEL,
            "source": "agnes-api",
        },
        {
            "id": "ollama",
            "label": "Ollama (本地)",
            "configured": ollama_ok,
            "models": ollama_models,
            "default_model": ollama_models[0] if ollama_models else "gemma2:2b",
            "source": "local",
        },
        {
            "id": "minimax",
            "label": "MiniMax",
            "configured": bool(os.getenv("MINIMAX_API_KEY")),
            "models": ["MiniMax-M2.7-highspeed"],
            "default_model": "MiniMax-M2.7-highspeed",
            "source": "local",
        },
        inf_provider,
        {
            "id": "mock",
            "label": "Mock (离线)",
            "configured": True,
            "models": [],
            "default_model": "",
            "source": "local",
        },
    ]
    model = ""
    if state.agent and hasattr(state.agent.llm, "model"):
        model = getattr(state.agent.llm, "model", "") or ""
    prefs = await state.store.get_user_prefs(user_id)
    active_models: list[str] = []
    for p in providers:
        if p["id"] == state.llm_mode:
            active_models = list(p.get("models") or [])
            break
    route = (prefs.get("llm_route") or "smart").strip().lower() or "smart"
    return web.json_response(
        {
            "mode": state.llm_mode,
            "model": model,
            "providers": providers,
            "source": "insforge" if state.llm_mode == "insforge" else "local",
            "user_prefs": {
                "llm_mode": prefs.get("llm_mode") or "",
                "llm_model": prefs.get("llm_model") or "",
                "llm_route": route,
                "llm_model_fast": prefs.get("llm_model_fast")
                or pick_default_fast(active_models, model),
                "llm_model_strong": prefs.get("llm_model_strong")
                or pick_default_strong(active_models, model),
            },
            "route": {
                "mode": route,
                "fast": prefs.get("llm_model_fast")
                or pick_default_fast(active_models, model),
                "strong": prefs.get("llm_model_strong")
                or pick_default_strong(active_models, model),
            },
            "insforge_error": inf_err,
        }
    )


@require_user
async def set_llm_settings(request: web.Request) -> web.Response:
    state = get_state(request)
    user_id = request["user"]["id"]
    body = await request.json()
    mode = (body.get("mode") or "").strip().lower()
    model = (body.get("model") or "").strip()
    if not mode:
        return web.json_response({"error": "mode required"}, status=400)
    try:
        await state.switch_llm(mode, model=model or None)
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"error": f"switch_failed: {exc}"}, status=502)

    patch: dict = {"llm_mode": mode, "llm_model": model}
    if "llm_route" in body and body.get("llm_route") is not None:
        patch["llm_route"] = str(body.get("llm_route") or "").strip().lower()
    if "llm_model_fast" in body and body.get("llm_model_fast") is not None:
        patch["llm_model_fast"] = str(body.get("llm_model_fast") or "").strip()
    if "llm_model_strong" in body and body.get("llm_model_strong") is not None:
        patch["llm_model_strong"] = str(body.get("llm_model_strong") or "").strip()

    try:
        current = await state.store.get_user_prefs(user_id)
        merged = merge_prefs(current, patch)
        await state.store.upsert_user_prefs(user_id, merged)
    except Exception as exc:  # noqa: BLE001
        print(f"[workbench] persist llm prefs failed ({exc})")

    return await get_llm_settings(request)


@require_user
async def get_prefs(request: web.Request) -> web.Response:
    state = get_state(request)
    prefs = await state.store.get_user_prefs(request["user"]["id"])
    return web.json_response({"prefs": prefs})


@require_user
async def patch_prefs(request: web.Request) -> web.Response:
    state = get_state(request)
    user_id = request["user"]["id"]
    body = await request.json()
    current = await state.store.get_user_prefs(user_id)
    merged = merge_prefs(current, body if isinstance(body, dict) else {})
    saved = await state.store.upsert_user_prefs(user_id, merged)
    return web.json_response({"prefs": saved})


def setup_settings_routes(app: web.Application) -> None:
    app.router.add_get("/api/settings/llm", get_llm_settings)
    app.router.add_post("/api/settings/llm", set_llm_settings)
    app.router.add_get("/api/settings/prefs", get_prefs)
    app.router.add_patch("/api/settings/prefs", patch_prefs)
