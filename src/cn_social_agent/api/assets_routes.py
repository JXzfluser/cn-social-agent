"""Topic asset aggregator API (read-only memory over journals + videos)."""

from __future__ import annotations

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.knowledge.assets import (
    gather_topic_assets_for_user,
    get_topic_asset,
)
from cn_social_agent.knowledge.topic_key import topic_key


async def _topics_for_request(request: web.Request) -> list:
    state = get_state(request)
    user = request["user"]
    user_id = user["id"]
    email = str(user.get("email") or "").strip()
    recent: list[str] = []
    try:
        prefs = await state.store.get_user_prefs(user_id)
        recent = list((prefs or {}).get("recent_topics") or [])
    except Exception:  # noqa: BLE001
        recent = []
    db = None
    if state.insforge is not None and state.store_mode == "insforge":
        db = state.insforge.db
    return await gather_topic_assets_for_user(
        user_id=user_id,
        email=email,
        store_mode=state.store_mode,
        insforge_db=db,
        recent_topics=recent,
    )


@require_user
async def list_topic_assets(request: web.Request) -> web.Response:
    topics = await _topics_for_request(request)
    summaries = []
    for t in topics:
        summaries.append(
            {
                "topic_key": t["topic_key"],
                "topic": t["topic"],
                "journal_count": t["journal_count"],
                "video_count": t["video_count"],
                "evidence_count": t["evidence_count"],
                "kinds": t.get("kinds") or [],
                "latest_ts": t.get("latest_ts") or "",
                "latest_journal_id": (t["journals"][0]["id"] if t["journals"] else None),
                "latest_video_id": (t["videos"][0]["id"] if t["videos"] else None),
            }
        )
    return web.json_response({"topics": summaries, "total": len(summaries)})


@require_user
async def get_topic_asset_detail(request: web.Request) -> web.Response:
    raw_key = (request.match_info.get("key") or "").strip()
    key = topic_key(raw_key) or raw_key.lower()
    if not key:
        return web.json_response({"error": "key required"}, status=400)
    topics = await _topics_for_request(request)
    asset = get_topic_asset(topics, key)
    if not asset:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response({"topic": asset})


def setup_assets_routes(app: web.Application) -> None:
    app.router.add_get("/api/topic-assets", list_topic_assets)
    app.router.add_get("/api/topic-assets/{key}", get_topic_asset_detail)
