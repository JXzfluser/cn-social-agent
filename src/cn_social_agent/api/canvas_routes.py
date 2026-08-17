"""Knowledge canvas API — standalone boards + per-project boards."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from aiohttp import web

from cn_social_agent.agent.loop import MockLLM
from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.content import canvas_store as cvs
from cn_social_agent.content import service as cps
from cn_social_agent.content.canvas import (
    KIND_LABELS,
    NODE_COLORS,
    NODE_KINDS,
    auto_arrange,
    canvas_stats,
    canvas_to_handoff,
    canvas_to_markdown,
    merge_seed_nodes,
    normalize_canvas,
    seed_nodes_from_project,
)
from cn_social_agent.content.canvas_ai import (
    OrganizeValidationError,
    build_organize_payload,
    merge_organize_result,
    select_nodes_for_organize,
    validate_organize_output,
)
from cn_social_agent.content.canvas_templates import (
    instantiate_canvas_template,
    list_canvas_templates,
)

log = logging.getLogger(__name__)


def _owner(request: web.Request) -> tuple[str, str]:
    user = request["user"]
    return str(user.get("id") or ""), str(user.get("email") or "")


async def _legacy_scratch(request: web.Request) -> dict[str, Any]:
    """One-time migration source: the old prefs-based scratch canvas."""
    state = get_state(request)
    try:
        prefs = await state.store.get_user_prefs(request["user"]["id"])
    except Exception:  # noqa: BLE001
        return {}
    scratch = (prefs or {}).get("canvas_scratch")
    return scratch if isinstance(scratch, dict) else {}


async def _default_board(request: web.Request) -> dict[str, Any]:
    user_id, email = _owner(request)
    return cvs.ensure_default_board(
        user_id=user_id, email=email, legacy=await _legacy_scratch(request)
    )


def _json_not_found(message: str) -> web.HTTPNotFound:
    return web.HTTPNotFound(
        text=json.dumps({"error": message}, ensure_ascii=False),
        content_type="application/json",
    )


async def _load_canvas(
    request: web.Request,
    project_id: str,
    board_id: str,
    *,
    strict: bool = False,
) -> tuple[dict[str, Any], Optional[dict[str, Any]]]:
    """Resolve the target canvas. ``strict`` refuses to fall back to the default board."""
    user_id, email = _owner(request)
    if project_id:
        project = await cps.get_project(project_id, user_id=user_id, email=email)
        if not project:
            if strict:
                raise _json_not_found("project not found")
            return normalize_canvas({}, project_id=project_id), None
        raw = project.get("canvas") if isinstance(project.get("canvas"), dict) else {}
        canvas = normalize_canvas(raw, project_id=project_id)
        canvas["title"] = str(project.get("short_topic") or project.get("topic") or "项目画布")
        return canvas, project
    if board_id:
        board = cvs.get_board(board_id, user_id=user_id, email=email)
        if board:
            return board, None
        if strict:
            raise _json_not_found("board not found")
    return await _default_board(request), None


async def _save_canvas(
    request: web.Request, project_id: str, canvas: dict[str, Any]
) -> dict[str, Any]:
    user_id, email = _owner(request)
    if project_id:
        payload = {
            "nodes": canvas["nodes"],
            "edges": canvas["edges"],
            "updated_at": canvas["updated_at"],
        }
        row = await cps.patch_project(
            project_id, {"canvas": payload}, user_id=user_id, email=email
        )
        if not row:
            raise web.HTTPNotFound(reason="project not found")
        saved = normalize_canvas(row.get("canvas"), project_id=project_id)
        saved["title"] = canvas.get("title") or ""
        return saved
    return cvs.save_board(
        {**canvas, "id": canvas.get("board_id") or ""}, user_id=user_id, email=email
    )


def _project_brief(project: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not project:
        return None
    pack = project.get("evidence_pack") if isinstance(project.get("evidence_pack"), dict) else {}
    return {
        "id": project.get("id"),
        "topic": project.get("topic"),
        "short_topic": project.get("short_topic"),
        "category": project.get("category"),
        "status": project.get("status"),
        "evidence_count": int(pack.get("count") or len(pack.get("evidences") or [])),
    }


def _board_summaries(request: web.Request) -> list[dict[str, Any]]:
    user_id, email = _owner(request)
    return [
        {
            "board_id": b["board_id"],
            "title": b["title"],
            "count": b["count"],
            "updated_at": b["updated_at"],
        }
        for b in cvs.list_boards(user_id=user_id, email=email)
    ]


def _canvas_response(
    request: web.Request, canvas: dict[str, Any], project: Optional[dict[str, Any]]
) -> web.Response:
    return web.json_response(
        {
            "canvas": canvas,
            "project": _project_brief(project),
            "boards": _board_summaries(request),
            "stats": canvas_stats(canvas),
            "kinds": [{"id": k, "label": KIND_LABELS.get(k, k)} for k in NODE_KINDS],
            "colors": list(NODE_COLORS),
        }
    )


async def _body(request: web.Request) -> dict[str, Any]:
    data = await request.json() if request.can_read_body else {}
    return data if isinstance(data, dict) else {}


@require_user
async def get_canvas(request: web.Request) -> web.Response:
    project_id = str(request.query.get("project_id") or "").strip()
    board_id = str(request.query.get("board_id") or "").strip()
    canvas, project = await _load_canvas(request, project_id, board_id)
    return _canvas_response(request, canvas, project)


@require_user
async def put_canvas(request: web.Request) -> web.Response:
    body = await _body(request)
    project_id = str(body.get("project_id") or "").strip()
    board_id = str(body.get("board_id") or "").strip()
    if not project_id and not board_id:
        board_id = (await _default_board(request))["board_id"]
    else:
        await _load_canvas(request, project_id, board_id, strict=True)
    canvas = normalize_canvas(
        {
            "nodes": body.get("nodes"),
            "edges": body.get("edges"),
            "title": body.get("title"),
        },
        project_id=project_id,
        board_id=board_id,
    )
    saved = await _save_canvas(request, project_id, canvas)
    return web.json_response({"ok": True, "canvas": saved, "stats": canvas_stats(saved)})


@require_user
async def arrange_canvas(request: web.Request) -> web.Response:
    body = await _body(request)
    project_id = str(body.get("project_id") or "").strip()
    board_id = str(body.get("board_id") or "").strip()
    canvas, project = await _load_canvas(request, project_id, board_id, strict=True)
    arranged = auto_arrange(canvas)
    arranged["title"] = canvas.get("title") or ""
    arranged["board_id"] = canvas.get("board_id") or ""
    saved = await _save_canvas(request, project_id, arranged)
    return _canvas_response(request, saved, project)


@require_user
async def export_canvas(request: web.Request) -> web.Response:
    project_id = str(request.query.get("project_id") or "").strip()
    board_id = str(request.query.get("board_id") or "").strip()
    canvas, project = await _load_canvas(request, project_id, board_id)
    title = canvas.get("title") or (project or {}).get("short_topic") or "知识画布"
    text = canvas_to_markdown(canvas, title=str(title))
    return web.Response(
        text=text,
        content_type="text/markdown",
        charset="utf-8",
        headers={"Content-Disposition": 'attachment; filename="canvas.md"'},
    )


@require_user
async def list_templates(request: web.Request) -> web.Response:
    return web.json_response({"templates": list_canvas_templates()})


@require_user
async def create_board(request: web.Request) -> web.Response:
    user_id, email = _owner(request)
    body = await _body(request)
    template_id = str(body.get("template_id") or "").strip()
    title = str(body.get("title") or "").strip() or "新画布"
    nodes: list[Any] = body.get("nodes") if isinstance(body.get("nodes"), list) else []
    edges: list[Any] = body.get("edges") if isinstance(body.get("edges"), list) else []
    if template_id:
        try:
            seeded = instantiate_canvas_template(template_id)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        nodes = seeded["nodes"]
        edges = seeded["edges"]
        if not str(body.get("title") or "").strip() and seeded.get("title"):
            title = str(seeded["title"])
    board = cvs.save_board(
        {
            "id": cvs.new_board_id(),
            "title": title,
            "nodes": nodes,
            "edges": edges,
        },
        user_id=user_id,
        email=email,
    )
    return _canvas_response(request, board, None)


def _organize_llm_available(state: Any) -> Any:
    """Return a non-mock LLM client when the workbench has one configured."""
    agent = getattr(state, "agent", None)
    llm = getattr(agent, "llm", None) if agent is not None else None
    if llm is None or isinstance(llm, MockLLM):
        return None
    if not hasattr(llm, "chat_completion"):
        return None
    return llm


@require_user
async def organize_canvas(request: web.Request) -> web.Response:
    """AI organize selected nodes. Never publishes; saves only after validation."""
    body = await _body(request)
    project_id = str(body.get("project_id") or "").strip()
    board_id = str(body.get("board_id") or "").strip()
    node_ids = body.get("node_ids") if isinstance(body.get("node_ids"), list) else []
    instruction = str(body.get("instruction") or "").strip()

    canvas, project = await _load_canvas(request, project_id, board_id, strict=True)
    selected = select_nodes_for_organize(canvas, node_ids)
    if not selected:
        return web.json_response({"error": "请先选中要整理的节点"}, status=400)

    state = get_state(request)
    llm = _organize_llm_available(state)
    if llm is None:
        log.warning("canvas organize unavailable: no configured workbench LLM")
        return web.json_response({"error": "AI 整理暂不可用"}, status=503)

    allowed = {n["id"] for n in selected}
    payload = build_organize_payload(
        canvas, [n["id"] for n in selected], instruction=instruction
    )
    messages = [
        {
            "role": "system",
            "content": (
                "你是知识画布整理助手。只返回严格 JSON 对象，"
                "键为 nodes 与 edges；必须保留全部节点 id，不得发布内容。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请按 instruction 整理下列节点，输出 JSON：\n"
                + json.dumps(payload, ensure_ascii=False)
            ),
        },
    ]
    try:
        resp = await llm.chat_completion(messages, temperature=0.3, max_tokens=4096)
        content = (
            ((resp.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        )
    except Exception as exc:  # noqa: BLE001 — transport/provider failure
        log.warning(
            "canvas organize LLM call failed: %s (nodes=%d)",
            type(exc).__name__,
            len(selected),
        )
        return web.json_response({"error": "AI 整理暂不可用"}, status=503)

    try:
        validated = validate_organize_output(content, allowed_ids=allowed)
    except OrganizeValidationError as exc:
        log.warning("canvas organize output rejected: %s (nodes=%d)", exc, len(selected))
        return web.json_response({"error": f"AI 整理结果无效：{exc}"}, status=422)

    merged = merge_organize_result(canvas, validated)
    merged["title"] = canvas.get("title") or ""
    merged["board_id"] = canvas.get("board_id") or ""
    saved = await _save_canvas(request, project_id, merged)
    return _canvas_response(request, saved, project)


@require_user
async def patch_board(request: web.Request) -> web.Response:
    user_id, email = _owner(request)
    board_id = str(request.match_info.get("id") or "").strip()
    board = cvs.get_board(board_id, user_id=user_id, email=email)
    if not board:
        return web.json_response({"error": "board not found"}, status=404)
    body = await _body(request)
    title = str(body.get("title") or "").strip()
    if title:
        board["title"] = title[:120]
    saved = cvs.save_board({**board, "id": board_id}, user_id=user_id, email=email)
    return _canvas_response(request, saved, None)


@require_user
async def delete_board(request: web.Request) -> web.Response:
    user_id, email = _owner(request)
    board_id = str(request.match_info.get("id") or "").strip()
    removed = cvs.delete_board(board_id, user_id=user_id, email=email)
    fallback = await _default_board(request)
    return web.json_response(
        {
            "ok": removed,
            "canvas": fallback,
            "boards": _board_summaries(request),
            "stats": canvas_stats(fallback),
        }
    )


@require_user
async def seed_canvas(request: web.Request) -> web.Response:
    """Pull topic / notes / evidences from the Content Project onto the board."""
    body = await _body(request)
    project_id = str(body.get("project_id") or "").strip()
    board_id = str(body.get("board_id") or "").strip()
    source_id = str(body.get("source_project_id") or "").strip() or project_id
    if not source_id:
        return web.json_response({"error": "project_id required"}, status=400)
    user_id, email = _owner(request)
    source = await cps.get_project(source_id, user_id=user_id, email=email)
    if not source:
        return web.json_response({"error": "project not found"}, status=404)
    canvas, project = await _load_canvas(request, project_id, board_id, strict=True)
    merged = merge_seed_nodes(canvas, seed_nodes_from_project(source))
    added = int(merged.pop("added", 0) or 0)
    merged["title"] = canvas.get("title") or ""
    merged["board_id"] = canvas.get("board_id") or ""
    saved = await _save_canvas(request, project_id, merged)
    return web.json_response(
        {
            "ok": True,
            "added": added,
            "canvas": saved,
            "project": _project_brief(project),
            "boards": _board_summaries(request),
            "stats": canvas_stats(saved),
        }
    )


@require_user
async def handoff_canvas(request: web.Request) -> web.Response:
    """Turn selected nodes into a workshop handoff (optionally creating a project)."""
    user_id, email = _owner(request)
    body = await _body(request)
    project_id = str(body.get("project_id") or "").strip()
    board_id = str(body.get("board_id") or "").strip()
    node_ids = body.get("node_ids") if isinstance(body.get("node_ids"), list) else []
    canvas, project = await _load_canvas(request, project_id, board_id, strict=True)
    payload = canvas_to_handoff(canvas, node_ids)
    if not payload["node_count"]:
        return web.json_response({"error": "画布为空或未选中节点"}, status=400)

    topic = str(body.get("topic") or "").strip() or payload["topic"]
    if not topic and project:
        topic = str(project.get("short_topic") or project.get("topic") or "")
    if not topic:
        topic = (payload["research_notes"].splitlines() or [""])[0][:60]

    created = None
    if not project_id and body.get("create_project"):
        created = await cps.create_project(
            topic=topic or "画布选题",
            user_id=user_id,
            email=email,
            category=str(body.get("category") or "").strip(),
            research_notes=payload["research_notes"],
            search_terms=payload["search_terms"] or None,
            source={"kind": "manual", "title": "知识画布", "name": "canvas"},
        )
        project_id = str(created.get("id") or "")

    return web.json_response(
        {
            "ok": True,
            "topic": topic,
            "research_notes": payload["research_notes"],
            "search_terms": payload["search_terms"],
            "urls": payload["urls"],
            "node_count": payload["node_count"],
            "content_project_id": project_id or "",
            "created_project": bool(created),
        }
    )


def setup_canvas_routes(app: web.Application) -> None:
    app.router.add_get("/api/canvas", get_canvas)
    app.router.add_put("/api/canvas", put_canvas)
    app.router.add_post("/api/canvas/arrange", arrange_canvas)
    app.router.add_get("/api/canvas/export", export_canvas)
    app.router.add_get("/api/canvas/templates", list_templates)
    app.router.add_post("/api/canvas/boards", create_board)
    app.router.add_patch("/api/canvas/boards/{id}", patch_board)
    app.router.add_delete("/api/canvas/boards/{id}", delete_board)
    app.router.add_post("/api/canvas/seed", seed_canvas)
    app.router.add_post("/api/canvas/handoff", handoff_canvas)
    app.router.add_post("/api/canvas/organize", organize_canvas)
