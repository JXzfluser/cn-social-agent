"""Hotspot board API — multi-source scan for Agent chat starters."""

from __future__ import annotations

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.tools.context import reset_tool_context, set_tool_context
from cn_social_agent.tools.hotspot_engine import attach_local_assets
from cn_social_agent.tools.hotspot_handoff import build_handoff_payload
from cn_social_agent.tools.hotspots import list_hotspot_sources, tool_scan_hotspot_board


@require_user
async def get_hotspots(request: web.Request) -> web.Response:
    q = request.rel_url.query
    try:
        days = int(q.get("days") or 60)
    except ValueError:
        days = 60
    try:
        min_stars = int(q.get("min_stars") or 500)
    except ValueError:
        min_stars = 500
    try:
        per_page = int(q.get("per_page") or 8)
    except ValueError:
        per_page = 8
    language = (q.get("language") or "").strip()
    source = (q.get("source") or "all").strip().lower() or "all"
    domain = (q.get("domain") or "all").strip().lower() or "all"

    state = get_state(request)
    user = request["user"]
    user_id = user["id"]
    email = str(user.get("email") or "").strip()
    prefs: dict = {}
    try:
        prefs = await state.store.get_user_prefs(user_id)
    except Exception:  # noqa: BLE001
        prefs = {}
    if not isinstance(prefs, dict):
        prefs = {}

    from cn_social_agent.content.connectors import (
        enabled_hotspot_sources,
        resolve_hotspot_source_filter,
    )

    effective, skipped = resolve_hotspot_source_filter(source, prefs)
    if effective == "none":
        data: dict = {
            "ok": True,
            "title": "热点榜（无启用源）",
            "hint": "热点看板连接器已关闭，或所选源未开启。到「连接器」面板调整。",
            "sources": list_hotspot_sources(),
            "source": source,
            "domain": domain,
            "board": [],
            "count": 0,
            "scored": True,
            "skipped_sources": skipped,
        }
    else:
        allowed = enabled_hotspot_sources(prefs)
        data = await tool_scan_hotspot_board(
            days=days,
            min_stars=min_stars,
            language=language,
            per_page=per_page,
            source=source if effective != "subset" else "all",
            domain=domain,
            allowed_sources=allowed,
        )
        if skipped:
            data["skipped_sources"] = skipped

    insforge_db = (
        state.insforge.db
        if state.insforge is not None and state.store_mode == "insforge"
        else None
    )
    ctx_token = set_tool_context(
        user_id=user_id,
        email=email,
        prefs=prefs,
        store_mode=state.store_mode,
        insforge_db=insforge_db,
    )
    try:
        board = data.get("board") or []
        if board:
            data["board"] = await attach_local_assets(board)
            data["count"] = len(data["board"])
    finally:
        reset_tool_context(ctx_token)

    if "sources" not in data:
        data["sources"] = list_hotspot_sources()
    status = 200 if data.get("ok") else 502
    return web.json_response(data, status=status)


@require_user
async def post_hotspot_handoff(request: web.Request) -> web.Response:
    user = request["user"]
    user_id = user["id"]
    email = str(user.get("email") or "").strip()
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 — malformed body
        body = {}
    if not isinstance(body, dict):
        body = {}
    out = await build_handoff_payload(
        title=str(body.get("title") or body.get("topic") or "").strip(),
        url=str(body.get("url") or "").strip(),
        source=str(body.get("source") or "").strip(),
        why=str(body.get("why") or "").strip(),
        topic_key=str(body.get("topic_key") or "").strip(),
        track=str(body.get("track") or "koubo").strip(),
        research_notes=str(body.get("research_notes") or "").strip(),
    )
    if not out.get("ok"):
        return web.json_response(out, status=400)

    # Always attach a Content Project so workshops share notes / evidence.
    try:
        from cn_social_agent.content import service as cps

        topic = str(out.get("short_topic") or out.get("topic") or "").strip()
        proj = await cps.create_project(
            topic=topic,
            user_id=user_id,
            email=email,
            category=str(out.get("category") or "").strip(),
            research_notes=str(out.get("research_notes") or "").strip(),
            search_terms=out.get("search_terms") if isinstance(out.get("search_terms"), list) else None,
            source={
                "kind": "hotspot",
                "url": str(out.get("url") or ""),
                "title": topic,
                "name": str(out.get("source") or ""),
            },
            why=str(out.get("why") or "").strip(),
            topic_key=str(out.get("topic_key") or "").strip(),
            url=str(out.get("url") or "").strip(),
        )
        out["content_project_id"] = proj["id"]
        out["short_topic"] = proj.get("short_topic") or topic
    except Exception as exc:  # noqa: BLE001 — handoff still works without project
        out["content_project_error"] = str(exc)[:160]

    return web.json_response(out, status=200)


def setup_hotspots_routes(app: web.Application) -> None:
    app.router.add_get("/api/hotspots", get_hotspots)
    app.router.add_post("/api/hotspots/handoff", post_hotspot_handoff)
