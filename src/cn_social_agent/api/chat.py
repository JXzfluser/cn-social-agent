from __future__ import annotations

import json

from aiohttp import web

from cn_social_agent.agent.mode import detect_mode
from cn_social_agent.agent.state import (
    normalize_agent_state,
    sync_todos_from_production_plan,
)
from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.api.prefs import (
    prefs_prompt_block,
    production_brief_from_messages,
    trim_messages_for_context,
)
from cn_social_agent.llm.router import resolve_chat_model
from cn_social_agent.usage.meter import KIND_LLM_CHAT, record_event


def _session_agent_state(app_state, session: dict) -> dict:
    sid = session.get("id") or ""
    raw = session.get("agent_state")
    if sid and sid in app_state.session_agent_state:
        cached = app_state.session_agent_state[sid]
        # Prefer richer of the two
        if raw:
            merged = {**normalize_agent_state(raw), **normalize_agent_state(cached)}
            # Keep todos from cache if production-bound
            if cached.get("todos"):
                merged["todos"] = cached["todos"]
            if cached.get("active_project_id"):
                merged["active_project_id"] = cached["active_project_id"]
            return normalize_agent_state(merged)
        return normalize_agent_state(cached)
    return normalize_agent_state(raw)


async def _persist_agent_state(app_state, user_id: str, session_id: str, agent_state: dict) -> dict:
    state = normalize_agent_state(agent_state)
    app_state.session_agent_state[session_id] = state
    try:
        await app_state.store.update_session(user_id, session_id, agent_state=state)
    except Exception:  # noqa: BLE001
        pass
    return state


@require_user
async def chat(request: web.Request) -> web.StreamResponse:
    state = get_state(request)
    assert state.agent is not None
    body = await request.json()
    session_id = body.get("session_id")
    content = (body.get("content") or "").strip()
    if not session_id or not content:
        return web.json_response(
            {"error": "session_id and content required"}, status=400
        )

    user_id = request["user"]["id"]
    session = await state.store.get_session(user_id, session_id)
    if not session:
        return web.json_response({"error": "session not found"}, status=404)

    await state.store.add_message(user_id, session_id, role="user", content=content)
    history = await state.store.list_messages(user_id, session_id)
    messages = [
        {"role": m["role"], "content": m.get("content") or "", "tool_calls": m.get("tool_calls")}
        for m in history
    ]
    # AgentLoop only needs role/content for LLM; keep tool_calls for mode detect
    llm_messages = [{"role": m["role"], "content": m.get("content") or ""} for m in messages]
    llm_messages = trim_messages_for_context(llm_messages, max_messages=24)

    bindings = await state.store.get_skill_bindings(user_id)
    pack = getattr(state, "pack", None)
    if pack is not None:
        from cn_social_agent.packs.loader import apply_pack_skills

        apply_pack_skills(state.skills, pack)
    for skill in state.skills._skills.values():
        if skill.id in bindings:
            skill.enabled = bindings[skill.id]

    prefs = await state.store.get_user_prefs(user_id)
    base_system = body.get("system_prompt") or session.get("system_prompt") or ""
    sys_extra = [base_system.strip()] if base_system.strip() else []
    brief = production_brief_from_messages(history)
    agent_state = _session_agent_state(state, session)
    # mode detect also sees prior tool names via history messages with tool_calls
    detect_msgs = []
    for m in history[-24:]:
        detect_msgs.append(
            {
                "role": m.get("role") or "",
                "content": m.get("content") or "",
                "tool_calls": m.get("tool_calls"),
            }
        )
    mode = detect_mode(
        detect_msgs if detect_msgs else llm_messages,
        agent_state=agent_state,
        brief=brief,
    )
    # Video prefs / production brief only in produce — keep research chats clean
    if mode == "produce":
        sys_extra.append(prefs_prompt_block(prefs))
        if brief:
            sys_extra.append(brief)
    # 资料库 RAG：先注入清单，再把与用户消息最相关的资料片段直接放进上下文
    try:
        from cn_social_agent.tools.reference_library import reference_library

        _lib = reference_library.list(user_id)
        if _lib:
            lines = "\n".join(f'- {i["name"]}（id: {i["id"]}）' for i in _lib[:10])
            rag_parts: list[str] = [
                f"用户资料库现有 {len(_lib)} 份参考资料：\n{lines}\n"
                "若需要完整原文：调用 library_read(id=\"...\")。"
                "不要让用户重新粘贴，不要用 http_get 等其他工具去找这些本地资料。"
            ]
            last_user_msg = ""
            for m in reversed(messages or []):
                if (m.get("role") or "") == "user" and (m.get("content") or "").strip():
                    last_user_msg = str(m["content"])
                    break
            if last_user_msg:
                hits = reference_library.retrieve(user_id, last_user_msg)
                for h in hits:
                    rag_parts.append(
                        f"【资料片段 · {h['name']}】（与本次提问相关度 {h['score']}，"
                        f"{'已截断，可用 library_read 读全文' if h['truncated'] else '完整片段'}）\n{h['snippet']}"
                    )
            if rag_parts:
                sys_extra.append("\n\n".join(rag_parts))
    except Exception:  # noqa: BLE001 — 提示注入失败不阻塞对话
        pass
    system_prompt = "\n\n".join(sys_extra)

    # Per-request model: Fast/Strong smart route (provider stays process-global)
    available: list[str] = []
    default_model = ""
    if state.agent and hasattr(state.agent.llm, "model"):
        default_model = str(getattr(state.agent.llm, "model", "") or "")
    if state.llm_mode == "agnes":
        try:
            from cn_social_agent.llm import AgnesLLM

            available = await AgnesLLM().list_chat_model_ids(limit=80)
        except Exception:  # noqa: BLE001
            available = []
    elif state.llm_mode == "ollama":
        try:
            from cn_social_agent.llm import OllamaLLM

            available = await OllamaLLM.list_model_ids(limit=40)
        except Exception:  # noqa: BLE001
            available = []
    elif state.llm_mode == "insforge" and state.insforge is not None:
        try:
            available = await state.insforge.llm.list_model_ids(limit=80)
        except Exception:  # noqa: BLE001
            available = []

    routed = resolve_chat_model(
        agent_mode=mode,
        prefs=prefs if isinstance(prefs, dict) else {},
        available_models=available,
        default_model=default_model,
        session_model=str(session.get("model") or ""),
        body_model=str(body.get("model") or ""),
    )
    use_model = routed.get("model") or ""

    try:
        reply = await state.agent.run(
            detect_msgs if detect_msgs else llm_messages,
            model=use_model,
            system_prompt=system_prompt,
            prefs=prefs if isinstance(prefs, dict) else {},
            agent_state=agent_state,
            brief=brief,
            user_id=user_id,
            email=str(request["user"].get("email") or "").strip(),
            store_mode=state.store_mode,
            insforge_db=(
                state.insforge.db
                if state.insforge is not None and state.store_mode == "insforge"
                else None
            ),
        )
    except Exception as exc:  # noqa: BLE001 — surface LLM provider errors
        return web.json_response(
            {
                "error": f"llm_failed: {exc}",
                "llm": state.llm_mode,
                "model_route": routed,
            },
            status=502,
        )

    record_event(
        KIND_LLM_CHAT,
        user_id=user_id,
        project_id=session_id,
        status="ok",
        meta={"mode": reply.mode, "llm": state.llm_mode},
    )

    # Sync todos from video project if bound
    new_state = reply.agent_state or agent_state
    pid = (new_state.get("active_project_id") or "").strip()
    production_plan = None
    if pid and state.insforge is not None and state.store_mode == "insforge":
        try:
            from cn_social_agent.video.plan import build_production_plan
            from cn_social_agent.video.store import VideoStore

            vs = VideoStore(state.insforge.db)
            project = await vs.get_project(user_id, pid)
            if project:
                scenes = await vs.list_scenes(pid)
                job = state.video_jobs.get(pid) or {}
                production_plan = build_production_plan(project, scenes, job)
                new_state = sync_todos_from_production_plan(new_state, production_plan)
        except Exception:  # noqa: BLE001
            pass

    new_state = await _persist_agent_state(state, user_id, session_id, new_state)

    saved = await state.store.add_message(
        user_id,
        session_id,
        role="assistant",
        content=reply.content,
        tool_calls=reply.tool_calls or None,
    )

    payload_extra = {
        "mode": reply.mode,
        "agent_state": new_state,
        "clarify": reply.clarify,
        "artifacts": reply.artifacts,
        "production_plan": production_plan,
        "model_route": routed,
        "llm": state.llm_mode,
    }

    want_sse = "text/event-stream" in request.headers.get("Accept", "")
    if not want_sse and not body.get("stream"):
        return web.json_response(
            {
                "message": saved,
                "tool_calls": reply.tool_calls,
                **payload_extra,
            }
        )

    resp = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
    await resp.prepare(request)

    chunk_size = 24
    text = reply.content or ""
    for i in range(0, max(len(text), 1), chunk_size):
        piece = text[i : i + chunk_size]
        piece_payload = json.dumps({"type": "delta", "content": piece}, ensure_ascii=False)
        await resp.write(f"data: {piece_payload}\n\n".encode("utf-8"))
    done = json.dumps(
        {
            "type": "done",
            "message": saved,
            "tool_calls": reply.tool_calls,
            **payload_extra,
        },
        ensure_ascii=False,
    )
    await resp.write(f"data: {done}\n\n".encode("utf-8"))
    await resp.write_eof()
    return resp


def setup_chat_routes(app: web.Application) -> None:
    app.router.add_post("/api/chat", chat)
