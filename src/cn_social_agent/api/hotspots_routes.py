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


@require_user
async def hotspot_angles(request: web.Request) -> web.Response:
    """LLM 为一条热点生成 3 个选题角度（对标新榜/蝉妈妈的选题建议）。"""
    import asyncio
    import json as _json
    import re as _re

    state = get_state(request)
    llm = getattr(state.agent, "llm", None) if state.agent else None
    if llm is None:
        return web.json_response({"error": "llm not configured"}, status=503)
    body = await request.json() if request.can_read_body else {}
    title = str(body.get("title") or "").strip()[:200]
    if not title:
        return web.json_response({"error": "title required"}, status=400)
    desc = str(body.get("description") or "").strip()[:400]
    source = str(body.get("source") or "").strip()[:40]
    system = (
        "你是内容策划。针对给定热点，面向中国程序员/独立开发者受众，提出 3 个差异化选题角度。"
        '只输出 JSON：{"angles":[{"title":"视频标题","angle":"切入角度一句话","why":"为什么现在做"}]}。'
        "角度要接地气：能蹭热度、能落到实操、或能给出反常识观点。"
    )
    user = f"热点来源：{source}\n热点标题：{title}\n热点摘要：{desc}"
    try:
        data = await asyncio.wait_for(
            llm.chat_completion(
                [{"role": "system", "content": system}, {"role": "user", "content": user}]
            ),
            timeout=90,
        )
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"error": f"llm_failed: {exc}"}, status=502)
    content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") if isinstance(data, dict) else data
    text = str(content or "")
    angles: list = []
    try:
        angles = _json.loads(text).get("angles") or []
    except _json.JSONDecodeError:
        m = _re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                angles = _json.loads(m.group(0)).get("angles") or []
            except _json.JSONDecodeError:
                angles = []
    angles = [a for a in angles if isinstance(a, dict) and str(a.get("title") or "").strip()][:3]
    if not angles:
        return web.json_response({"error": "empty angles, try again"}, status=502)
    return web.json_response({"ok": True, "angles": angles})


def setup_hotspots_routes(app: web.Application) -> None:
    app.router.add_get("/api/hotspots", get_hotspots)
    app.router.add_post("/api/hotspots/handoff", post_hotspot_handoff)
    app.router.add_post("/api/hotspots/angles", hotspot_angles)
