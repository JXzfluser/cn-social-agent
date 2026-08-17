from __future__ import annotations

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user


@require_user
async def list_or_create(request: web.Request) -> web.Response:
    state = get_state(request)
    user_id = request["user"]["id"]
    if request.method == "GET":
        rows = await state.store.list_sessions(user_id)
        return web.json_response({"sessions": rows})

    body = await request.json() if request.can_read_body else {}
    row = await state.store.create_session(
        user_id,
        title=body.get("title") or "New chat",
        system_prompt=body.get("system_prompt") or "",
        model=body.get("model") or "",
    )
    return web.json_response(row, status=201)


@require_user
async def get_session(request: web.Request) -> web.Response:
    state = get_state(request)
    user_id = request["user"]["id"]
    sid = request.match_info["id"]
    row = await state.store.get_session(user_id, sid)
    if not row:
        return web.json_response({"error": "not found"}, status=404)
    messages = await state.store.list_messages(user_id, sid)
    from cn_social_agent.agent.state import normalize_agent_state

    agent_state = normalize_agent_state(
        state.session_agent_state.get(sid) or row.get("agent_state")
    )
    return web.json_response(
        {"session": row, "messages": messages, "agent_state": agent_state}
    )


@require_user
async def delete_session(request: web.Request) -> web.Response:
    state = get_state(request)
    ok = await state.store.delete_session(request["user"]["id"], request.match_info["id"])
    if not ok:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response({"success": True})


@require_user
async def patch_session(request: web.Request) -> web.Response:
    state = get_state(request)
    body = await request.json()
    row = await state.store.update_session(
        request["user"]["id"],
        request.match_info["id"],
        **body,
    )
    if not row:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(row)


def setup_session_routes(app: web.Application) -> None:
    app.router.add_route("GET", "/api/sessions", list_or_create)
    app.router.add_route("POST", "/api/sessions", list_or_create)
    app.router.add_get("/api/sessions/{id}", get_session)
    app.router.add_delete("/api/sessions/{id}", delete_session)
    app.router.add_patch("/api/sessions/{id}", patch_session)
