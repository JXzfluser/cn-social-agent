"""参考资料库 HTTP 路由（按用户 RLS 隔离）。"""

from __future__ import annotations

from aiohttp import web

from cn_social_agent.api.deps import require_user
from cn_social_agent.tools.reference_library import LibraryError, reference_library


@require_user
async def list_library(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    return web.json_response({"items": reference_library.list(user_id)})


@require_user
async def upload_library(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    body = await request.json()
    try:
        item = reference_library.add(
            user_id,
            name=str(body.get("name") or ""),
            content=str(body.get("content") or ""),
        )
    except LibraryError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    return web.json_response(item, status=201)


@require_user
async def get_library_item(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    item = reference_library.get(user_id, request.match_info["id"])
    if item is None:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response({"item": item})


@require_user
async def delete_library_item(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    ok = reference_library.delete(user_id, request.match_info["id"])
    if not ok:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response({"ok": True})


def setup_library_routes(app: web.Application) -> None:
    app.router.add_get("/api/library", list_library)
    app.router.add_post("/api/library", upload_library)
    app.router.add_get("/api/library/{id}", get_library_item)
    app.router.add_delete("/api/library/{id}", delete_library_item)
