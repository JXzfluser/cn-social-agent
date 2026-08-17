"""Knowledge card workshop API (scan + history + publish)."""

from __future__ import annotations

import os

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.cards.categories import list_categories
from cn_social_agent.cards.history import (
    delete_history_item,
    get_history_item,
)
from cn_social_agent.cards.publish.images import save_uploaded_images
from cn_social_agent.cards.publish.service import publish_card
from cn_social_agent.cards.service import run_compose, run_research, run_scan
from cn_social_agent.usage.meter import (
    KIND_CARD_COMPOSE,
    KIND_CARD_PUBLISH,
    record_event,
)

_ALLOWED_PLATFORMS = frozenset({"weixin", "toutiao", "mock"})


def _mock_allowed(request: web.Request) -> bool:
    if os.getenv("CARD_PUBLISH_ALLOW_MOCK", "").strip() in ("1", "true", "yes"):
        return True
    return get_state(request).llm_mode == "mock"


@require_user
async def categories(_request: web.Request) -> web.Response:
    return web.json_response({"categories": list_categories()})


@require_user
async def scan(request: web.Request) -> web.Response:
    state = get_state(request)
    body = await request.json() if request.can_read_body else {}
    user = request["user"]
    user_id = user["id"]
    email = str(user.get("email") or "").strip()
    model = ""
    if state.agent and getattr(state.agent, "llm", None) is not None:
        model = str(getattr(state.agent.llm, "model", "") or "")
    model = (body.get("model") or model or "").strip()
    category = str(body.get("category") or "hiring_insight").strip()
    edition = body.get("edition")
    if edition is None:
        edition = body.get("edition_no")

    try:
        payload = await run_scan(
            body.get("roles") or body.get("topics"),
            category=category,
            use_workbench_llm=True,
            workbench_llm=state.agent.llm if state.agent else None,
            workbench_model=model,
            user_id=user_id,
            email=email,
            edition=edition,
        )
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"error": str(exc)}, status=502)
    # Surface current LLM for UI
    payload["llm"] = {
        "mode": state.llm_mode,
        "model": model,
    }
    return web.json_response(payload)


@require_user
async def research(request: web.Request) -> web.Response:
    body = await request.json() if request.can_read_body else {}
    user = request["user"]
    user_id = user["id"]
    email = str(user.get("email") or "").strip()
    category = str(body.get("category") or "hiring_insight").strip()
    edition = body.get("edition")
    if edition is None:
        edition = body.get("edition_no")

    append_pack = None
    append_id = str(body.get("appendPackId") or "").strip()
    if append_id:
        from cn_social_agent.cards.cloud import get_card_record

        prev = await get_card_record(append_id, user_id=user_id, email=email)
        if not prev:
            prev = get_history_item(append_id, user_id=user_id, email=email)
        if prev and isinstance(prev.get("evidencePack"), dict):
            append_pack = prev["evidencePack"]

    seeds = body.get("seedEvidences") or body.get("seed_evidences")
    if seeds is not None and not isinstance(seeds, list):
        seeds = None
    terms = body.get("searchTerms") or body.get("search_terms")
    if terms is not None and not isinstance(terms, list):
        terms = None

    try:
        payload = await run_research(
            body.get("roles") or body.get("topics"),
            category=category,
            depth="deep",
            append_pack=append_pack,
            append_history_id=append_id or None,
            user_id=user_id,
            email=email,
            edition=edition,
            research_notes=str(body.get("research_notes") or body.get("researchNotes") or "").strip(),
            seed_evidences=seeds,
            search_terms=terms,
            source=str(body.get("source") or "").strip(),
            url=str(body.get("url") or "").strip(),
        )
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"error": str(exc)}, status=502)

    # Write evidence back into the Content Project when present.
    cpid = str(body.get("content_project_id") or body.get("contentProjectId") or "").strip()
    if cpid and payload.get("evidencePack"):
        try:
            from cn_social_agent.content import service as cps

            patch: dict[str, Any] = {
                "evidence_pack": payload["evidencePack"],
                "category": payload.get("category") or category,
                "status": "researching",
            }
            notes_in = str(
                body.get("research_notes") or body.get("researchNotes") or ""
            ).strip()
            if notes_in:
                patch["research_notes"] = notes_in
            await cps.patch_project(cpid, patch, user_id=user_id, email=email)
            if payload.get("id") or payload.get("packId"):
                await cps.attach_artifacts(
                    cpid,
                    user_id=user_id,
                    email=email,
                    journal_id=str(payload.get("id") or payload.get("packId") or ""),
                )
            payload["content_project_id"] = cpid
        except Exception:  # noqa: BLE001
            pass
    return web.json_response(payload)


@require_user
async def compose(request: web.Request) -> web.Response:
    state = get_state(request)
    body = await request.json() if request.can_read_body else {}
    user = request["user"]
    user_id = user["id"]
    email = str(user.get("email") or "").strip()
    model = ""
    if state.agent and getattr(state.agent, "llm", None) is not None:
        model = str(getattr(state.agent.llm, "model", "") or "")
    model = (body.get("model") or model or "").strip()
    category = str(body.get("category") or "hiring_insight").strip()
    edition = body.get("edition")
    if edition is None:
        edition = body.get("edition_no")

    pack_id = str(body.get("packId") or body.get("pack_id") or "").strip() or None
    evidences = body.get("evidences")
    if evidences is not None and not isinstance(evidences, list):
        evidences = None
    allowed = body.get("evidenceIdsAllowed") or body.get("evidence_ids_allowed")
    if allowed is not None and not isinstance(allowed, list):
        allowed = None

    try:
        payload = await run_compose(
            body.get("roles") or body.get("topics"),
            pack_id=pack_id,
            evidences=evidences,
            evidence_ids_allowed=allowed,
            category=category,
            use_workbench_llm=True,
            workbench_llm=state.agent.llm if state.agent else None,
            workbench_model=model,
            user_id=user_id,
            email=email,
            edition=edition,
            persist=True,
            min_selected=5,
        )
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"error": str(exc)}, status=502)
    if payload.get("ok") is False:
        return web.json_response(payload, status=400)
    payload["llm"] = {
        "mode": state.llm_mode,
        "model": model,
    }
    record_event(
        KIND_CARD_COMPOSE,
        user_id=user_id,
        project_id=str(payload.get("id") or pack_id or ""),
        status="ok",
        meta={"category": category},
    )

    # S3: quality_pass → mark content project export_ready (never auto-publish)
    cpid = str(body.get("content_project_id") or body.get("contentProjectId") or "").strip()
    if payload.get("quality_gate_pass") and cpid:
        try:
            prefs = await state.store.get_user_prefs(user_id)
        except Exception:  # noqa: BLE001
            prefs = {}
        from cn_social_agent.content.automations import is_automation_enabled
        from cn_social_agent.content import service as cps

        if is_automation_enabled(prefs if isinstance(prefs, dict) else {}, "quality_pass_mark_export"):
            try:
                await cps.patch_project(
                    cpid,
                    {
                        "status": "export_ready",
                        "quality": {
                            "export_ready": True,
                            "gate_pass": True,
                            "rejected": False,
                            "hint": "成刊质检已通过，可导出 PNG（不会自动发布）",
                        },
                    },
                    user_id=user_id,
                    email=email,
                )
                await cps.attach_artifacts(
                    cpid,
                    user_id=user_id,
                    email=email,
                    journal_id=str(payload.get("id") or pack_id or ""),
                )
                payload["content_project_id"] = cpid
                payload["export_ready"] = True
                payload["automation_hint"] = "已标记可导出，请在工坊确认后导出"
            except Exception:  # noqa: BLE001
                pass
    return web.json_response(payload)


@require_user
async def history(request: web.Request) -> web.Response:
    user = request["user"]
    user_id = user["id"]
    email = str(user.get("email") or "").strip()
    item_id = (request.rel_url.query.get("id") or "").strip()
    if item_id:
        from cn_social_agent.cards.cloud import get_card_record

        rec = await get_card_record(item_id, user_id=user_id, email=email)
        if not rec:
            rec = get_history_item(item_id, user_id=user_id, email=email)
        if not rec:
            return web.json_response({"error": "not found"}, status=404)
        return web.json_response(rec)

    from cn_social_agent.cards.cloud import list_card_records
    from cn_social_agent.cards.history import _merge_rows, load_history

    cloud_rows = await list_card_records(user_id=user_id, email=email)
    local_rows = load_history(user_id, email=email)
    merged = _merge_rows(cloud_rows, local_rows)
    out: list[dict] = []
    for r in merged:
        if not isinstance(r, dict):
            continue
        cover = r.get("cover") if isinstance(r.get("cover"), dict) else {}
        knowledge = r.get("knowledge") if isinstance(r.get("knowledge"), list) else []
        pubs = r.get("publish") if isinstance(r.get("publish"), list) else []
        out.append(
            {
                "id": r.get("id"),
                "ts": r.get("ts"),
                "title": cover.get("title") or "",
                "mode": r.get("mode") or "cached",
                "category": r.get("category") or "hiring_insight",
                "snippetCount": r.get("snippetCount") or 0,
                "topics": [
                    k.get("topicTitle") or "" for k in knowledge if isinstance(k, dict)
                ],
                "dateLabel": cover.get("edition") or cover.get("gradientPart") or "",
                "edition": cover.get("edition") or r.get("edition") or "",
                "publish": [
                    {
                        "platform": p.get("platform"),
                        "status": p.get("status"),
                        "message": p.get("message"),
                    }
                    for p in pubs[-3:]
                    if isinstance(p, dict)
                ],
            }
        )
    return web.json_response(out[:100])


@require_user
async def delete_history(request: web.Request) -> web.Response:
    user = request["user"]
    user_id = user["id"]
    email = str(user.get("email") or "").strip()
    item_id = (request.match_info.get("id") or "").strip()
    if not item_id:
        return web.json_response({"error": "id required"}, status=400)
    from cn_social_agent.cards.cloud import delete_card_record

    cloud_ok = await delete_card_record(item_id, user_id=user_id, email=email)
    local_ok = delete_history_item(item_id, user_id=user_id, email=email)
    if not cloud_ok and not local_ok:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response({"ok": True, "id": item_id})


async def cards_page(request: web.Request) -> web.Response:
    """Legacy URL → main workbench card mode."""
    q = request.rel_url.query
    loc = "/?mode=card"
    item_id = (q.get("id") or "").strip()
    if item_id:
        loc = f"/?mode=card&id={item_id}"
    raise web.HTTPFound(loc)


@require_user
async def export_images(request: web.Request) -> web.Response:
    """Multipart: history_id + files (png)."""
    reader = await request.multipart()
    history_id = ""
    files: list[tuple[str, bytes]] = []
    while True:
        part = await reader.next()
        if part is None:
            break
        name = part.name or ""
        if name == "history_id":
            history_id = (await part.text()).strip()
        elif name in ("files", "files[]", "file"):
            raw = await part.read(decode=False)
            fname = part.filename or f"{len(files):02d}.png"
            files.append((fname, raw))
    if not history_id:
        return web.json_response({"error": "history_id required"}, status=400)
    if not files:
        return web.json_response({"error": "no files"}, status=400)
    paths = save_uploaded_images(history_id, files)
    return web.json_response(
        {"ok": True, "history_id": history_id, "count": len(paths)}
    )


@require_user
async def publish(request: web.Request) -> web.Response:
    body = await request.json() if request.can_read_body else {}
    user = request["user"]
    history_id = str(body.get("history_id") or "").strip()
    if not history_id:
        return web.json_response({"error": "history_id required"}, status=400)
    platforms = body.get("platforms") or []
    if not isinstance(platforms, list) or not platforms:
        return web.json_response({"error": "platforms required"}, status=400)
    cleaned: list[str] = []
    for p in platforms:
        key = str(p or "").strip().lower()
        if key not in _ALLOWED_PLATFORMS:
            return web.json_response({"error": f"invalid platform: {p}"}, status=400)
        if key == "mock" and not _mock_allowed(request):
            return web.json_response({"error": "mock not allowed"}, status=403)
        cleaned.append(key)
    try:
        out = await publish_card(
            history_id=history_id,
            platforms=cleaned,
            direct=bool(body.get("direct")),
            title_override=str(body.get("title") or ""),
            user_id=user["id"],
            email=str(user.get("email") or "").strip(),
        )
    except RuntimeError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"error": str(exc)}, status=502)
    record_event(
        KIND_CARD_PUBLISH,
        user_id=user["id"],
        project_id=history_id,
        status="ok",
        meta={"platforms": cleaned},
    )
    return web.json_response(out)


def setup_card_routes(app: web.Application) -> None:
    app.router.add_get("/cards", cards_page)
    app.router.add_get("/api/cards/categories", categories)
    app.router.add_post("/api/cards/scan", scan)
    app.router.add_post("/api/cards/research", research)
    app.router.add_post("/api/cards/compose", compose)
    app.router.add_get("/api/cards/history", history)
    app.router.add_delete("/api/cards/history/{id}", delete_history)
    app.router.add_post("/api/cards/export-images", export_images)
    app.router.add_post("/api/cards/publish", publish)
