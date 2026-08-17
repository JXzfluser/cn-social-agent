from __future__ import annotations

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.api.store import new_id


@require_user
async def upload_media(request: web.Request) -> web.Response:
    state = get_state(request)
    reader = await request.multipart()
    field = await reader.next()
    if field is None:
        return web.json_response({"error": "file required"}, status=400)

    filename = field.filename or "upload.bin"
    mime = field.headers.get("Content-Type", "application/octet-stream")
    data = await field.read()
    key = f"{request['user']['id']}/{new_id()}_{filename}"

    if state.store_mode == "insforge" and state.insforge is not None:
        try:
            await state.insforge.storage.upload(
                "workbench", key, data, content_type=mime, upsert=True
            )
            storage_path = f"workbench/{key}"
        except Exception as exc:  # noqa: BLE001
            return web.json_response({"error": f"upload failed: {exc}"}, status=502)
    else:
        # Memory mode: keep metadata only (no durable binary).
        storage_path = f"memory://{key}"

    row = await state.store.add_media(request["user"]["id"], storage_path, mime)
    return web.json_response(row, status=201)


def setup_media_routes(app: web.Application) -> None:
    app.router.add_post("/api/media", upload_media)
