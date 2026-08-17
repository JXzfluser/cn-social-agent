from __future__ import annotations

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user


@require_user
async def list_tools(request: web.Request) -> web.Response:
    state = get_state(request)
    return web.json_response({"tools": state.tools.list_tools()})


def setup_tools_routes(app: web.Application) -> None:
    app.router.add_get("/api/tools", list_tools)
