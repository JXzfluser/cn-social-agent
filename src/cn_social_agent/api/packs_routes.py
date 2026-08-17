"""Active content pack API."""

from __future__ import annotations

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.packs.loader import get_active_pack, packs_dir


@require_user
async def get_active(request: web.Request) -> web.Response:
    state = get_state(request)
    pack = getattr(state, "pack", None) or get_active_pack()
    return web.json_response(
        {
            "pack": pack.to_dict() if pack else None,
            "packs_dir": str(packs_dir()),
        }
    )


def setup_packs_routes(app: web.Application) -> None:
    app.router.add_get("/api/packs/active", get_active)
