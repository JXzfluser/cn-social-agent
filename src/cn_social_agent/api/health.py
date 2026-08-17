from __future__ import annotations

import os

from aiohttp import web

from cn_social_agent.api.deps import get_state


def _insforge_console_url() -> str:
    """Dashboard UI port (7131), not the API (7130).

    Hitting the API root redirects to /dashboard/login which 404s on the
    backend-only process — the real SPA is served on INSFORGE_AUTH_PORT.
    """
    explicit = (os.getenv("INSFORGE_CONSOLE_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    port = (os.getenv("INSFORGE_AUTH_PORT") or "7131").strip() or "7131"
    return f"http://localhost:{port}"


async def health(request: web.Request) -> web.Response:
    state = get_state(request)
    insforge_ok = False
    if state.insforge is not None:
        try:
            insforge_ok = await state.insforge.auth.health()
        except Exception:  # noqa: BLE001
            insforge_ok = False
    console = _insforge_console_url()
    used_for: list[str] = []
    if getattr(state, "auth_mode", "") == "insforge":
        used_for.append("auth")
    if state.store_mode == "insforge":
        if "auth" not in used_for:
            used_for.append("auth")
        used_for.append("store")
    if state.llm_mode == "insforge":
        used_for.append("llm")
    return web.json_response(
        {
            "status": "ok",
            "store": state.store_mode,
            "auth": getattr(state, "auth_mode", state.store_mode),
            "llm": state.llm_mode,
            "model": getattr(getattr(state.agent, "llm", None), "model", "") or "",
            "insforge": {
                "configured": state.insforge is not None,
                "healthy": insforge_ok,
                "console_url": console,
                "used_for": used_for,
            },
            "skills": len(state.skills.list_skills()),
            "tools": len(state.tools.list_tools()),
        }
    )


def setup_health_routes(app: web.Application) -> None:
    app.router.add_get("/health", health)
