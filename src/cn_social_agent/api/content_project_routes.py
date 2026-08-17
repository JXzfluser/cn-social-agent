"""Content Project HTTP API."""

from __future__ import annotations

from aiohttp import web

from cn_social_agent.api.deps import require_user
from cn_social_agent.content import service as cps


@require_user
async def list_or_create(request: web.Request) -> web.Response:
    user = request["user"]
    user_id = user["id"]
    email = str(user.get("email") or "").strip()
    if request.method == "GET":
        rows = await cps.list_projects(user_id=user_id, email=email)
        return web.json_response({"projects": rows, "count": len(rows)})

    body = await request.json() if request.can_read_body else {}
    topic = str(body.get("topic") or body.get("short_topic") or "").strip()
    if not topic:
        return web.json_response({"error": "topic required"}, status=400)
    source = body.get("source") if isinstance(body.get("source"), dict) else None
    if not source and (body.get("url") or body.get("source_kind")):
        source = {
            "kind": str(body.get("source_kind") or "manual"),
            "url": str(body.get("url") or ""),
            "title": str(body.get("source_title") or ""),
            "name": str(body.get("source") or "") if isinstance(body.get("source"), str) else "",
        }
    row = await cps.create_project(
        topic=topic,
        user_id=user_id,
        email=email,
        category=str(body.get("category") or "").strip(),
        research_notes=str(body.get("research_notes") or "").strip(),
        search_terms=body.get("search_terms") if isinstance(body.get("search_terms"), list) else None,
        source=source,
        why=str(body.get("why") or "").strip(),
        topic_key=str(body.get("topic_key") or "").strip(),
        url=str(body.get("url") or "").strip(),
    )
    return web.json_response(row, status=201)


@require_user
async def get_one(request: web.Request) -> web.Response:
    user = request["user"]
    pid = str(request.match_info.get("id") or "").strip()
    row = await cps.get_project(pid, user_id=user["id"], email=str(user.get("email") or ""))
    if not row:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(row)


@require_user
async def patch_one(request: web.Request) -> web.Response:
    user = request["user"]
    pid = str(request.match_info.get("id") or "").strip()
    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        body = {}
    row = await cps.patch_project(
        pid, body, user_id=user["id"], email=str(user.get("email") or "")
    )
    if not row:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(row)


@require_user
async def attach(request: web.Request) -> web.Response:
    user = request["user"]
    pid = str(request.match_info.get("id") or "").strip()
    body = await request.json() if request.can_read_body else {}
    row = await cps.attach_artifacts(
        pid,
        user_id=user["id"],
        email=str(user.get("email") or ""),
        journal_id=body.get("journal_id") if "journal_id" in body else None,
        video_id=body.get("video_id") if "video_id" in body else None,
        presentation_id=body.get("presentation_id") if "presentation_id" in body else None,
    )
    if not row:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(row)


@require_user
async def board_view(request: web.Request) -> web.Response:
    user = request["user"]
    from cn_social_agent.content.board import (
        LANE_LABELS,
        collect_categories,
        filter_projects,
        group_projects_by_lane,
        sort_projects,
    )

    include_rejected = str(request.rel_url.query.get("rejected") or "1") not in ("0", "false", "no")
    query = str(request.rel_url.query.get("q") or request.rel_url.query.get("query") or "").strip()
    category = str(request.rel_url.query.get("category") or "").strip()
    artifact = str(request.rel_url.query.get("artifact") or "").strip()
    sort = str(request.rel_url.query.get("sort") or "updated_desc").strip()

    rows = await cps.list_projects(user_id=user["id"], email=str(user.get("email") or ""), limit=80)
    lanes = group_projects_by_lane(rows, include_rejected=include_rejected)
    filtered = {
        lane: sort_projects(
            filter_projects(cards, query=query, category=category, artifact=artifact),
            sort,
        )
        for lane, cards in lanes.items()
    }
    counts = {k: len(v) for k, v in filtered.items()}
    flat = [c for cards in filtered.values() for c in cards]
    return web.json_response(
        {
            "lanes": filtered,
            "counts": counts,
            "labels": LANE_LABELS,
            "total": sum(counts.values()),
            "categories": collect_categories(flat),
            "query": {"q": query, "category": category, "artifact": artifact, "sort": sort},
        }
    )


@require_user
async def board_move(request: web.Request) -> web.Response:
    """Move a project onto a board lane (candidate / active / export_ready / rejected)."""
    user = request["user"]
    pid = str(request.match_info.get("id") or "").strip()
    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        body = {}
    lane = str(body.get("lane") or body.get("status") or "").strip()
    reason = str(body.get("reason") or body.get("reject_reason") or "").strip()

    from cn_social_agent.content.board import apply_lane_move, board_card

    cur = await cps.get_project(pid, user_id=user["id"], email=str(user.get("email") or ""))
    if not cur:
        return web.json_response({"error": "not found"}, status=404)
    try:
        patch = apply_lane_move(cur, lane, reason=reason)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)
    row = await cps.patch_project(
        pid, patch, user_id=user["id"], email=str(user.get("email") or "")
    )
    if not row:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response({"ok": True, "project": board_card(row), "raw": row})


@require_user
async def delete_one(request: web.Request) -> web.Response:
    user = request["user"]
    pid = str(request.match_info.get("id") or "").strip()
    from cn_social_agent.content import cloud as cloud_mod
    from cn_social_agent.content import store_local as local

    email = str(user.get("email") or "")
    ok_local = local.delete_project(pid, user_id=user["id"], email=email)
    ok_cloud = False
    try:
        ok_cloud = await cloud_mod.delete_content_record(
            pid, user_id=user["id"], email=email
        )
    except Exception:  # noqa: BLE001
        ok_cloud = False
    if not ok_local and not ok_cloud:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response({"ok": True, "id": pid})


def setup_content_project_routes(app: web.Application) -> None:
    app.router.add_get("/api/content-projects", list_or_create)
    app.router.add_post("/api/content-projects", list_or_create)
    app.router.add_get("/api/content-projects/board", board_view)
    app.router.add_get("/api/content-projects/{id}", get_one)
    app.router.add_patch("/api/content-projects/{id}", patch_one)
    app.router.add_delete("/api/content-projects/{id}", delete_one)
    app.router.add_post("/api/content-projects/{id}/attach", attach)
    app.router.add_post("/api/content-projects/{id}/board", board_move)
