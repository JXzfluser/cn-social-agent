"""Content Project routes — project CRUD read-only + knowledge lineage."""

from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.content import service as cps

TABLE_NOTES = "wb_topic_notes"
TABLE_WORKFLOWS = "wb_topic_workflow_records"
TABLE_SKILLS = "wb_topic_skills"


@require_user
async def list_content_projects(request: web.Request) -> web.Response:
    """GET /api/content/projects?limit=40&status= — user's content projects."""
    user = request["user"]
    try:
        limit = max(1, min(100, int(request.query.get("limit") or "40")))
    except ValueError:
        limit = 40
    status = (request.query.get("status") or "").strip()
    rows = await cps.list_projects(user_id=user["id"], email=user.get("email") or "", limit=limit)
    if status:
        rows = [r for r in rows if str(r.get("status") or "") == status]
    out = [
        {
            "id": r.get("id"),
            "topic": r.get("topic"),
            "short_topic": r.get("short_topic"),
            "category": r.get("category"),
            "status": r.get("status"),
            "topic_key": r.get("topic_key"),
            "knowledge_used_count": len(r.get("knowledge_used") or []),
            "artifacts": r.get("artifacts") or {},
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
        }
        for r in rows
    ]
    return web.json_response({"projects": out, "count": len(out)})


@require_user
async def get_content_project(request: web.Request) -> web.Response:
    """GET /api/content/{id} — single project detail."""
    user = request["user"]
    pid = (request.match_info.get("id") or "").strip()
    if not pid:
        return web.json_response({"error": "project id required"}, status=400)
    p = await cps.get_project(pid, user_id=user["id"], email=user.get("email") or "")
    if not p:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(p)


@require_user
async def record_content_knowledge(request: web.Request) -> web.Response:
    """POST /api/content/{id}/knowledge — append Know-How entries to lineage."""
    user = request["user"]
    pid = (request.match_info.get("id") or "").strip()
    if not pid:
        return web.json_response({"error": "project id required"}, status=400)
    body = await request.json() if request.can_read_body else {}
    items = body.get("items")
    if not isinstance(items, list) or not items:
        return web.json_response({"error": "items list required"}, status=400)
    p = await cps.record_knowledge_used(
        pid, items, user_id=user["id"], email=user.get("email") or ""
    )
    if not p:
        return web.json_response({"error": "record failed"}, status=500)
    return web.json_response({"ok": True, "knowledge_used": p.get("knowledge_used") or []})


@require_user
async def delete_content_project(request: web.Request) -> web.Response:
    """DELETE /api/content/{id} — remove a content project."""
    user = request["user"]
    pid = (request.match_info.get("id") or "").strip()
    if not pid:
        return web.json_response({"error": "project id required"}, status=400)
    ok = await cps.delete_project(pid, user_id=user["id"], email=user.get("email") or "")
    if not ok:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response({"ok": True})


async def _resolve_knowledge_items(
    db: Any, user_id: str, items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Resolve lineage refs to live Know-How records (title/preview/topic)."""
    resolved: list[dict[str, Any]] = []
    if db is None:
        return [{"type": i.get("type"), "id": i.get("id"), "title": i.get("title"), "exists": False} for i in items]

    note_ids = [i["id"] for i in items if i.get("type") == "note"]
    wf_ids = [i["id"] for i in items if i.get("type") == "workflow"]
    skill_ids = [i["id"] for i in items if i.get("type") == "skill"]

    notes_by_id: dict[str, dict] = {}
    wfs_by_id: dict[str, dict] = {}
    skills_by_id: dict[str, dict] = {}

    async def _fetch_notes() -> None:
        if not note_ids:
            return
        rows = await db.query(TABLE_NOTES, filters={"user_id": f"eq.{user_id}"}, limit=2000)
        for r in rows or []:
            if str(r.get("id")) in note_ids:
                notes_by_id[str(r.get("id"))] = r

    async def _fetch_workflows() -> None:
        if not wf_ids:
            return
        rows = await db.query(TABLE_WORKFLOWS, filters={"user_id": f"eq.{user_id}"}, limit=2000)
        for r in rows or []:
            if str(r.get("id")) in wf_ids:
                wfs_by_id[str(r.get("id"))] = r

    async def _fetch_skills() -> None:
        if not skill_ids:
            return
        rows = await db.query(TABLE_SKILLS, filters={"user_id": f"eq.{user_id}"}, limit=2000)
        for r in rows or []:
            if str(r.get("id")) in skill_ids:
                skills_by_id[str(r.get("id"))] = r

    await asyncio.gather(_fetch_notes(), _fetch_workflows(), _fetch_skills())

    for i in items:
        ktype = i.get("type")
        kid = str(i.get("id") or "")
        if ktype == "note" and kid in notes_by_id:
            r = notes_by_id[kid]
            resolved.append(
                {
                    "type": "note",
                    "id": kid,
                    "title": (r.get("content") or i.get("title") or "")[:80],
                    "topic_key": r.get("topic_key"),
                    "updated_at": r.get("updated_at"),
                    "exists": True,
                }
            )
        elif ktype == "workflow" and kid in wfs_by_id:
            r = wfs_by_id[kid]
            resolved.append(
                {
                    "type": "workflow",
                    "id": kid,
                    "title": (r.get("method") or r.get("title") or i.get("title") or "")[:80],
                    "topic_key": r.get("topic_key"),
                    "updated_at": r.get("updated_at"),
                    "exists": True,
                }
            )
        elif ktype == "skill" and kid in skills_by_id:
            r = skills_by_id[kid]
            resolved.append(
                {
                    "type": "skill",
                    "id": kid,
                    "title": (r.get("skill_name") or i.get("title") or "")[:80],
                    "topic_key": r.get("topic_key"),
                    "updated_at": r.get("updated_at"),
                    "exists": True,
                }
            )
        else:
            resolved.append(
                {
                    "type": ktype,
                    "id": kid,
                    "title": i.get("title") or "",
                    "exists": ktype in ("journal", "video"),
                }
            )
    return resolved


@require_user
async def content_lineage(request: web.Request) -> web.Response:
    """GET /api/content/{id}/lineage — knowledge sources + produced artifacts."""
    state = get_state(request)
    user = request["user"]
    pid = (request.match_info.get("id") or "").strip()
    if not pid:
        return web.json_response({"error": "project id required"}, status=400)
    p = await cps.get_project(pid, user_id=user["id"], email=user.get("email") or "")
    if not p:
        return web.json_response({"error": "not found"}, status=404)

    db = state.insforge.db if state.insforge else None
    sources = await _resolve_knowledge_items(db, user["id"], p.get("knowledge_used") or [])

    arts = p.get("artifacts") or {}
    outputs: list[dict[str, Any]] = []
    if arts.get("journal_id"):
        outputs.append({"type": "journal", "id": arts["journal_id"], "title": "知识卡片"})
    if arts.get("video_id"):
        outputs.append({"type": "video", "id": arts["video_id"], "title": "短视频"})
    if arts.get("presentation_id"):
        outputs.append({"type": "presentation", "id": arts["presentation_id"], "title": "演示"})

    return web.json_response(
        {
            "project": {
                "id": p.get("id"),
                "topic": p.get("topic"),
                "short_topic": p.get("short_topic"),
                "category": p.get("category"),
                "status": p.get("status"),
                "topic_key": p.get("topic_key"),
                "created_at": p.get("created_at"),
                "updated_at": p.get("updated_at"),
            },
            "sources": sources,
            "outputs": outputs,
        }
    )


@require_user
async def knowledge_usage(request: web.Request) -> web.Response:
    """GET /api/knowhow/usage/{type}/{id} — reverse lineage: projects using an entry."""
    user = request["user"]
    itype = (request.match_info.get("type") or "").strip()
    iid = (request.match_info.get("id") or "").strip()
    if not iid:
        return web.json_response({"error": "item id required"}, status=400)
    rows = await cps.projects_using_knowledge(
        itype, iid, user_id=user["id"], email=user.get("email") or ""
    )
    out = [
        {
            "id": r.get("id"),
            "topic": r.get("topic"),
            "short_topic": r.get("short_topic"),
            "category": r.get("category"),
            "status": r.get("status"),
            "updated_at": r.get("updated_at"),
        }
        for r in rows
    ]
    return web.json_response({"used_by": out, "count": len(out)})


@require_user
async def list_content_projects_full(request: web.Request) -> web.Response:
    """GET /api/content-projects — full project records (legacy path, canvas/context bar)."""
    user = request["user"]
    rows = await cps.list_projects(user_id=user["id"], email=user.get("email") or "", limit=60)
    return web.json_response({"projects": rows, "items": rows, "count": len(rows)})


@require_user
async def create_content_project(request: web.Request) -> web.Response:
    """POST /api/content/projects — create a content project (optionally with lineage)."""
    user = request["user"]
    body = await request.json() if request.can_read_body else {}
    topic = str(body.get("topic") or "").strip()
    if not topic:
        return web.json_response({"error": "topic required"}, status=400)
    ku = body.get("knowledge_used")
    p = await cps.create_project(
        topic=topic,
        user_id=user["id"],
        email=user.get("email") or "",
        category=str(body.get("category") or ""),
        research_notes=str(body.get("research_notes") or ""),
        source=body.get("source") if isinstance(body.get("source"), dict) else None,
        why=str(body.get("why") or ""),
        topic_key=str(body.get("topic_key") or ""),
        url=str(body.get("url") or ""),
        knowledge_used=ku if isinstance(ku, list) else None,
    )
    return web.json_response(p, status=201)


def setup_content_routes(app: web.Application) -> None:
    app.router.add_get("/api/content-projects", list_content_projects_full)
    app.router.add_get("/api/content/projects", list_content_projects)
    app.router.add_post("/api/content/projects", create_content_project)
    app.router.add_get("/api/content/{id}/lineage", content_lineage)
    app.router.add_get("/api/content/{id}", get_content_project)
    app.router.add_delete("/api/content/{id}", delete_content_project)
    app.router.add_post("/api/content/{id}/knowledge", record_content_knowledge)
    app.router.add_get("/api/knowhow/usage/{type}/{id}", knowledge_usage)
