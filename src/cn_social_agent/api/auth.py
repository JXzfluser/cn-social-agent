from __future__ import annotations

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.insforge import InsForgeError


async def login(request: web.Request) -> web.Response:
    body = await request.json()
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if not email or not password:
        return web.json_response({"error": "email and password required"}, status=400)

    state = get_state(request)
    if state.auth_mode == "memory":
        state.memory.ensure_demo_user()
        result = state.memory.login_user(email, password)
        if not result:
            # First-run convenience: auto-register unknown local users
            if email not in state.memory.users:
                state.memory.register_user(email, password)
                result = state.memory.login_user(email, password)
        if not result:
            return web.json_response(
                {
                    "error": "invalid credentials",
                    "hint": "本地模式可用 demo@local.test / demo123456，或点注册",
                },
                status=401,
            )
        return web.json_response(result)

    if state.insforge is None:
        return web.json_response(
            {"error": "InsForge auth unavailable", "hint": "后端未连接 InsForge"},
            status=503,
        )
    try:
        data = await state.insforge.auth.login(email, password)
    except InsForgeError as exc:
        return web.json_response({"error": str(exc)}, status=exc.status_code or 401)
    return web.json_response(data)


async def register(request: web.Request) -> web.Response:
    body = await request.json()
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if not email or not password:
        return web.json_response({"error": "email and password required"}, status=400)

    state = get_state(request)
    if state.auth_mode == "memory":
        if email in state.memory.users:
            return web.json_response({"error": "user exists"}, status=409)
        user = state.memory.register_user(email, password)
        result = state.memory.login_user(email, password)
        return web.json_response({"user": user, **(result or {})})

    if state.insforge is None:
        return web.json_response(
            {"error": "InsForge auth unavailable", "hint": "后端未连接 InsForge"},
            status=503,
        )
    extra = {}
    name = (body.get("name") or "").strip()
    if name:
        extra["name"] = name
    try:
        data = await state.insforge.auth.register(email, password, **extra)
    except InsForgeError as exc:
        return web.json_response({"error": str(exc)}, status=exc.status_code or 400)
    return web.json_response(data)


@require_user
async def me(request: web.Request) -> web.Response:
    return web.json_response({"user": request["user"]})


@require_user
async def logout(request: web.Request) -> web.Response:
    state = get_state(request)
    token = request["access_token"]
    if state.auth_mode == "memory":
        state.memory.tokens.pop(token, None)
        return web.json_response({"success": True})
    if state.insforge is None:
        return web.json_response({"success": True})
    try:
        await state.insforge.auth.logout(token)
    except Exception:  # noqa: BLE001
        pass
    return web.json_response({"success": True})


def setup_auth_routes(app: web.Application) -> None:
    app.router.add_post("/api/auth/login", login)
    app.router.add_post("/api/auth/register", register)
    app.router.add_post("/api/auth/logout", logout)
    app.router.add_get("/api/auth/me", me)
