"""Shared dependencies for the workbench API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from aiohttp import web

from cn_social_agent.agent.loop import AgentLoop, MockLLM
from cn_social_agent.api.store import InsForgeStore, MemoryStore, Store
from cn_social_agent.core.memory_backend import memory_client
from cn_social_agent.experts.registry import ExpertRegistry
from cn_social_agent.insforge import InsForge
from cn_social_agent.llm import AgnesLLM, MiniMaxLLM, OllamaLLM
from cn_social_agent.skills.loader import SkillLoader
from cn_social_agent.tools import ToolRegistry, register_builtin_tools


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def skills_dir() -> Path:
    return project_root() / "skills"


async def _resolve_llm_mode() -> str:
    mode = os.getenv("WORKBENCH_LLM", "auto").lower()
    if mode != "auto":
        return mode
    # Prefer Agnes when configured — better tool calling than local small models.
    if AgnesLLM.configured():
        return "agnes"
    if os.getenv("INSFORGE_OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY"):
        return "insforge"
    if await OllamaLLM.available():
        return "ollama"
    if os.getenv("MINIMAX_API_KEY"):
        return "minimax"
    return "mock"


def _build_llm(mode: str, model: Optional[str] = None) -> Any:
    if mode == "agnes":
        if not AgnesLLM.configured():
            raise ValueError("Agnes 未配置：请设置 AGNES_API_KEY 或 config/default.yaml llm.api_key")
        return AgnesLLM(model=model or None)
    if mode == "insforge":
        raise ValueError("insforge LLM must be built with InsForge instance")
    if mode == "ollama":
        llm = OllamaLLM()
        if model:
            llm.model = model
        return llm
    if mode == "minimax":
        if not os.getenv("MINIMAX_API_KEY"):
            raise ValueError("MiniMax 未配置：请设置 MINIMAX_API_KEY")
        return MiniMaxLLM(model=model or None)
    if mode == "mock":
        return MockLLM()
    raise ValueError(f"unknown llm mode: {mode}")


async def _sync_platform_env_to_secrets() -> None:
    """Push WEIXIN_/TOUTIAO_ env credentials into InsForge Secrets when present."""
    from cn_social_agent.platforms.tokens import save_platform_config

    wx_id = (os.getenv("WEIXIN_APP_ID") or "").strip()
    wx_sec = (os.getenv("WEIXIN_APP_SECRET") or "").strip()
    if wx_id and wx_sec:
        await save_platform_config(
            "weixin",
            {
                "app_id": wx_id,
                "app_secret": wx_sec,
                "author": (os.getenv("WEIXIN_DRAFT_AUTHOR") or "").strip(),
                "source": "env",
            },
        )
    tt_id = (os.getenv("TOUTIAO_APP_ID") or "").strip()
    tt_sec = (os.getenv("TOUTIAO_APP_SECRET") or "").strip()
    if tt_id and tt_sec:
        await save_platform_config(
            "toutiao",
            {
                "app_id": tt_id,
                "app_secret": tt_sec,
                "redirect_uri": (os.getenv("TOUTIAO_REDIRECT_URI") or "").strip(),
                "source": "env",
            },
        )


class AppState:
    def __init__(self) -> None:
        self.store_mode = os.getenv("WORKBENCH_STORE", "memory").lower()
        self.auth_mode = os.getenv("WORKBENCH_AUTH", "auto").lower()
        self.llm_mode = os.getenv("WORKBENCH_LLM", "auto").lower()
        self.memory = MemoryStore()
        self.insforge: Optional[InsForge] = None
        self.store: Store = self.memory
        self.tools = ToolRegistry()
        register_builtin_tools(self.tools)
        self.skills = SkillLoader(skills_dir())
        self.skills.scan()
        self.pack = None
        try:
            from cn_social_agent.packs.loader import activate_pack, apply_pack_skills

            self.pack = activate_pack()
            if self.pack is not None:
                apply_pack_skills(self.skills, self.pack)
                print(
                    f"[workbench] pack={self.pack.id} "
                    f"skills_enabled={len(self.pack.skills_enabled)} "
                    f"templates={len(self.pack.templates)}"
                )
            else:
                print("[workbench] pack=none")
        except Exception as exc:  # noqa: BLE001
            print(f"[workbench] pack load skipped ({exc})")
        self.agent: Optional[AgentLoop] = None
        self.video_jobs: dict[str, Any] = {}
        # Fallback when DB has no agent_state column
        self.session_agent_state: dict[str, dict[str, Any]] = {}
        # Nexus expert workbench: tenant client + expert catalogue.
        self.nexus_client: Any = None
        self.nexus_registry: Optional[ExpertRegistry] = None

    async def startup(self) -> None:
        self.llm_mode = await _resolve_llm_mode()

        # Always try InsForge when enabled — needed for Secrets (platform config / OAuth)
        need_insforge = (
            self.store_mode == "insforge"
            or self.llm_mode == "insforge"
            or os.getenv("INSFORGE_ENABLED", "true").lower() == "true"
        )
        if need_insforge:
            self.insforge = InsForge()
            try:
                if self.insforge.enabled:
                    await self.insforge.initialize()
            except Exception:  # noqa: BLE001
                pass

        # Wire Secrets backend for card platform publish (InsForge first, local fallback)
        try:
            from cn_social_agent.platforms.tokens import set_secrets_backend

            if self.insforge is not None and getattr(self.insforge, "secrets", None):
                set_secrets_backend(self.insforge.secrets)
                print("[workbench] platform secrets → InsForge")
            else:
                set_secrets_backend(None)
                print("[workbench] platform secrets → local data/oauth (InsForge unavailable)")

            # Sync env platform credentials into InsForge Secrets (+ local mirror)
            await _sync_platform_env_to_secrets()
            try:
                from cn_social_agent.platforms.tokens import probe_secrets_backend

                st = await probe_secrets_backend()
                print(f"[workbench] secrets probe: {st.get('message')}")
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            print(f"[workbench] platform secrets init skipped ({exc})")

        # Wire card history → InsForge DB when reachable (even if session store falls back)
        try:
            from cn_social_agent.cards.cloud import set_card_db

            if self.insforge is not None and getattr(self.insforge, "db", None):
                set_card_db(self.insforge.db)
                print("[workbench] card history → InsForge (wb_card_history)")
            else:
                set_card_db(None)
        except Exception as exc:  # noqa: BLE001
            print(f"[workbench] card cloud init skipped ({exc})")

        try:
            from cn_social_agent.content.cloud import set_content_db

            if self.insforge is not None and getattr(self.insforge, "db", None):
                set_content_db(self.insforge.db)
                print("[workbench] content projects → InsForge (wb_content_projects)")
            else:
                set_content_db(None)
        except Exception as exc:  # noqa: BLE001
            print(f"[workbench] content project cloud init skipped ({exc})")

        if self.store_mode == "insforge" and self.insforge is not None:
            try:
                await self.insforge.db.query("wb_sessions", limit=1)
                self.store = InsForgeStore(self.insforge.db)
            except Exception as exc:  # noqa: BLE001
                print(f"[workbench] InsForge store unavailable ({exc}); falling back to memory")
                self.store = self.memory
                self.store_mode = "memory"
        else:
            self.store = self.memory
            self.store_mode = "memory"

        # Auth: InsForge-primary when healthy; memory only via WORKBENCH_AUTH=memory or auth down
        auth_override = os.getenv("WORKBENCH_AUTH", "auto").lower()
        insforge_auth_ok = False
        if self.insforge is not None:
            try:
                insforge_auth_ok = await self.insforge.auth.health()
            except Exception:  # noqa: BLE001
                insforge_auth_ok = False
        if auth_override == "memory":
            self.auth_mode = "memory"
        elif auth_override == "insforge":
            self.auth_mode = "insforge" if insforge_auth_ok else "memory"
            if not insforge_auth_ok:
                print("[workbench] WORKBENCH_AUTH=insforge but InsForge auth down → memory")
        elif insforge_auth_ok:
            self.auth_mode = "insforge"
        else:
            self.auth_mode = "memory"

        if self.auth_mode == "memory":
            self.memory.ensure_demo_user()
            print("[workbench] demo login: demo@local.test / demo123456")
        else:
            print("[workbench] auth → InsForge (register/login via backend)")

        # Nexus expert workbench: same isolation client the request code uses.
        # Memory auth → in-process RLS-emulating client (always runnable,
        # still isolated per user). InsForge auth → the real PostgREST client.
        if self.insforge is not None and self.auth_mode != "memory":
            self.nexus_client = self.insforge._client
            print("[workbench] nexus → InsForge (RLS-enforced)")
        else:
            self.nexus_client = memory_client(self.memory.user_id_for_token)
            print("[workbench] nexus → memory backend (RLS-emulated)")
        try:
            self.nexus_registry = ExpertRegistry().scan()
            print(f"[workbench] nexus experts: {len(self.nexus_registry)} loaded")
        except Exception as exc:  # noqa: BLE001
            self.nexus_registry = ExpertRegistry()
            print(f"[workbench] nexus registry empty ({exc})")

        try:
            if self.llm_mode == "insforge" and self.insforge is not None:
                llm: Any = self.insforge.llm
            else:
                llm = _build_llm(self.llm_mode)
        except Exception as exc:  # noqa: BLE001
            print(f"[workbench] LLM {self.llm_mode} failed ({exc}); falling back to mock")
            llm = MockLLM()
            self.llm_mode = "mock"

        self.agent = AgentLoop(llm=llm, tools=self.tools, skills=self.skills)
        print(f"[workbench] store={self.store_mode} auth={self.auth_mode} llm={self.llm_mode}")

    async def switch_llm(self, mode: str, model: Optional[str] = None) -> None:
        mode = mode.lower().strip()
        if mode == "insforge":
            if self.insforge is None:
                self.insforge = InsForge()
                if self.insforge.enabled:
                    await self.insforge.initialize()
            if self.insforge is None or not getattr(self.insforge, "llm", None):
                raise ValueError("InsForge LLM 不可用（需 OPENROUTER / InsForge AI Key）")
            llm: Any = self.insforge.llm
            if model:
                llm.model = model
        else:
            llm = _build_llm(mode, model=model)
        self.llm_mode = mode
        if self.agent is None:
            self.agent = AgentLoop(llm=llm, tools=self.tools, skills=self.skills)
        else:
            self.agent.llm = llm
        print(f"[workbench] switched llm={self.llm_mode} model={model or getattr(llm, 'model', '')}")

    async def shutdown(self) -> None:
        if self.insforge is not None:
            await self.insforge.close()


def get_state(request: web.Request) -> AppState:
    return request.app["state"]


def _extract_access_token(request: web.Request) -> str:
    """Bearer header, then cookie, then query — so same-origin iframes can auth."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        tok = auth[7:].strip()
        if tok:
            return tok
    cookie = request.cookies.get("wb_token") or request.cookies.get("access_token") or ""
    if cookie.strip():
        # Frontend may have stored encodeURIComponent(token)
        from urllib.parse import unquote

        return unquote(cookie.strip())
    # iframe / asset subrequests may only carry query token on the first HTML load;
    # prefer short query names used by the workbench preview.
    for key in ("access_token", "token", "wb_token"):
        q = (request.query.get(key) or "").strip()
        if q:
            return q
    return ""


def require_user(handler):
    async def wrapped(request: web.Request) -> web.Response:
        state = get_state(request)
        token = _extract_access_token(request)
        if not token:
            return web.json_response({"error": "unauthorized"}, status=401)

        user: Optional[dict[str, Any]] = None
        # Prefer InsForge token validation when auth_mode is insforge
        if state.auth_mode == "insforge" and state.insforge is not None:
            u = await state.insforge.auth.get_current_user(token)
            if u:
                user = {"id": u.id, "email": u.email}
        elif state.auth_mode == "memory" or state.store_mode == "memory":
            uid = state.memory.user_id_for_token(token)
            if uid:
                email = next(
                    (u["email"] for u in state.memory.users.values() if u["id"] == uid),
                    "",
                )
                user = {"id": uid, "email": email}
        elif state.insforge is not None:
            u = await state.insforge.auth.get_current_user(token)
            if u:
                user = {"id": u.id, "email": u.email}

        if not user:
            return web.json_response({"error": "unauthorized"}, status=401)
        request["user"] = user
        request["access_token"] = token
        return await handler(request)

    return wrapped
