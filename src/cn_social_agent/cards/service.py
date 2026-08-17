"""Orchestrate scan → cards → history."""

from __future__ import annotations

from typing import Any, Optional

from cn_social_agent.cards.build import build_cards, format_edition
from cn_social_agent.cards.categories import DEFAULT_TOPICS, get_category
from cn_social_agent.cards.evidence import (
    build_pack,
    merge_packs,
    selected_evidences,
    validate_evidence_ids,
)
from cn_social_agent.cards.history import get_history_item, save_history_record
from cn_social_agent.cards.llm import compose_with_llm
from cn_social_agent.cards.scrape import describe_scan_stats, scan_roles


def parse_roles(raw: Any, *, category: str = "hiring_insight") -> list[str]:
    if isinstance(raw, list):
        roles = [str(s).strip() for s in raw if str(s).strip()]
    else:
        text = str(raw or "")
        roles = [s.strip() for s in re_split_roles(text) if s.strip()]
    if not roles:
        roles = list(DEFAULT_TOPICS.get(get_category(category)["id"]) or DEFAULT_TOPICS["hiring_insight"])
    return roles


def re_split_roles(text: str) -> list[str]:
    import re

    return re.split(r"[、,，]", text)


def _flatten_scan_rows(rows: list[Any]) -> list[dict[str, Any]]:
    """Flatten scan_roles output; wrap leftover strings as text dicts."""
    flat: list[dict[str, Any]] = []
    for role_rows in rows or []:
        if not isinstance(role_rows, (list, tuple)):
            role_rows = [role_rows]
        for item in role_rows:
            if isinstance(item, dict):
                flat.append(item)
            else:
                t = str(item or "").strip()
                if t:
                    flat.append({"text": t})
    return flat


async def run_research(
    roles_raw: Any,
    *,
    category: str = "hiring_insight",
    depth: str = "deep",
    append_pack: Optional[dict[str, Any]] = None,
    append_history_id: Optional[str] = None,
    persist: bool = True,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    edition: Any = None,
    research_notes: str = "",
    seed_evidences: Optional[list[Any]] = None,
    search_terms: Optional[list[Any]] = None,
    source: str = "",
    url: str = "",
    min_seed: int = 5,
) -> dict[str, Any]:
    """Seed-first research → evidence pack (no LLM compose).

    Handoff path (Agent / hotspot): notes → seed evidence; scrape only tops
    up when seeds are thin, and top-up rows must pass a topic-relevance gate
    so they stay on subject. Manual path: distill a short topic from the
    pasted roles so long titles don't poison the search.
    """
    from cn_social_agent.cards.topic import (
        extract_short_topic,
        is_topic_relevant,
        seed_evidences_from_notes,
        topic_terms,
    )

    cat = get_category(category)
    roles = parse_roles(roles_raw, category=cat["id"])[:3]
    limit = 40 if depth == "deep" else 12

    primary = roles[0] if roles else ""
    short_topic = extract_short_topic(primary, research_notes) or primary
    terms = topic_terms(short_topic, source)

    # 1) Seeds: explicit rows first, else derive from fetched notes.
    seed_rows: list[dict[str, Any]] = []
    if seed_evidences:
        seed_rows = [dict(e) for e in seed_evidences if isinstance(e, dict) and e.get("text")]
        for e in seed_rows:
            e.setdefault("engine", "seed")
            e.setdefault("role", short_topic)
    elif research_notes:
        seed_rows = seed_evidences_from_notes(
            research_notes, topic=short_topic, source=source, url=url
        )
    seed_pack = build_pack(seed_rows, limit=limit, category=cat["id"]) if seed_rows else {
        "evidences": [],
        "count": 0,
    }

    # 2) Top-up scrape only when seeds are thin. Search the short topic (or
    #    explicit terms), never the full long title.
    scan_stats: list[dict[str, Any]] = []
    scrape_pack: dict[str, Any] = {"evidences": [], "count": 0}
    if seed_pack["count"] < min_seed:
        explicit = [str(t).strip() for t in (search_terms or []) if str(t or "").strip()]
        subjects = explicit or ([short_topic] if short_topic else roles) or roles
        if not explicit and not short_topic:
            subjects = roles
        rows = await scan_roles(
            subjects[:3], category=cat["id"], depth=depth, stats_out=scan_stats
        )
        flat = _flatten_scan_rows(rows)
        # Relevance gate: keep only rows that share subject signal, and mark
        # survivors so the packer keeps them even when signal-light.
        gated: list[dict[str, Any]] = []
        for r in flat:
            # Gate on the prominent lead, not the full 400 chars, so an
            # off-topic result can't sneak in on an incidental deep match.
            if is_topic_relevant(str(r.get("text") or "")[:140], terms):
                gated.append({**r, "relevant": True})
        scrape_pack = build_pack(gated, limit=limit, category=cat["id"])

    pack = merge_packs(seed_pack, scrape_pack, limit=limit, category=cat["id"])
    if append_pack:
        pack = merge_packs(append_pack, pack, limit=limit, category=cat["id"])

    ed = format_edition(edition, user_id=user_id, email=email)
    if pack["count"] == 0:
        detail = describe_scan_stats(scan_stats)
        payload: dict[str, Any] = {
            "ok": False,
            "error": f"未采到可用证据。来源状态：{detail}" if detail else "未采到可用证据（已过滤词典/导航噪声）",
            "evidencePack": pack,
            "roles": roles,
            "category": cat["id"],
            "mode": "research",
            "snippetCount": 0,
            "sources": [],
        }
    else:
        payload = {
            "ok": True,
            "evidencePack": pack,
            "roles": roles,
            "category": cat["id"],
            "mode": "research",
            "snippetCount": pack["count"],
            "sources": [e["text"] for e in pack["evidences"][:6]],
        }

    cover = {"title": cat["default_title"], "edition": ed}
    payload["cover"] = cover
    payload["edition"] = ed
    payload["knowledge"] = []

    if persist:
        rec = {
            "roles": roles,
            "category": cat["id"],
            "cover": cover,
            "knowledge": [],
            "sources": payload.get("sources") or [],
            "mode": "research",
            "snippetCount": payload.get("snippetCount") or 0,
            "edition": ed,
            "evidencePack": pack,
            "ok": payload.get("ok"),
        }
        if payload.get("error"):
            rec["error"] = payload["error"]
        if append_history_id:
            rec["id"] = str(append_history_id)
        saved = save_history_record(rec, user_id=user_id, email=email)
        payload["id"] = saved["id"]
        payload["packId"] = saved["id"]
        try:
            from cn_social_agent.cards.cloud import upsert_card_record

            ok = await upsert_card_record(saved, user_id=user_id, email=email)
            payload["persisted"] = "insforge" if ok else "local"
        except Exception:  # noqa: BLE001
            payload["persisted"] = "local"
    else:
        payload["persisted"] = "none"

    return payload


def _apply_evidence_selection(
    pack: dict[str, Any],
    *,
    evidences: Optional[list[Any]] = None,
    evidence_ids_allowed: Optional[list[Any]] = None,
) -> dict[str, Any]:
    """Sync selected flags from an evidences list and/or allow-list of ids."""
    pack = {
        "evidences": [dict(e) for e in (pack.get("evidences") or []) if isinstance(e, dict)],
        "count": int(pack.get("count") or 0),
    }
    if evidences:
        by_id = {
            str(e.get("id")): e
            for e in evidences
            if isinstance(e, dict) and e.get("id")
        }
        by_text = {
            str(e.get("text") or ""): e
            for e in evidences
            if isinstance(e, dict) and e.get("text")
        }
        for e in pack["evidences"]:
            src = by_id.get(str(e.get("id"))) or by_text.get(str(e.get("text") or ""))
            if src is not None and "selected" in src:
                e["selected"] = bool(src.get("selected"))
    if evidence_ids_allowed is not None:
        allowed = {str(i) for i in evidence_ids_allowed if str(i).strip()}
        for e in pack["evidences"]:
            e["selected"] = str(e.get("id")) in allowed
    pack["count"] = len(pack["evidences"])
    return pack


async def _resolve_evidence_pack(
    *,
    evidence_pack: Optional[dict[str, Any]] = None,
    pack_id: Optional[str] = None,
    evidences: Optional[list[Any]] = None,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> dict[str, Any]:
    if isinstance(evidence_pack, dict) and (
        evidence_pack.get("evidences") is not None or evidence_pack.get("count") is not None
    ):
        pack = {
            "evidences": list(evidence_pack.get("evidences") or []),
            "count": int(
                evidence_pack.get("count")
                if evidence_pack.get("count") is not None
                else len(evidence_pack.get("evidences") or [])
            ),
        }
        return pack

    if evidences:
        raw = [e for e in evidences if isinstance(e, dict)]
        # If items already look like pack rows (have id), keep as pack
        if raw and all(e.get("id") for e in raw):
            pack = {"evidences": [dict(e) for e in raw], "count": len(raw)}
            return pack
        return build_pack(raw)

    pid = str(pack_id or "").strip()
    if pid:
        prev: Optional[dict[str, Any]] = None
        try:
            from cn_social_agent.cards.cloud import get_card_record

            prev = await get_card_record(pid, user_id=user_id, email=email)
        except Exception:  # noqa: BLE001
            prev = None
        if not prev:
            prev = get_history_item(pid, user_id=user_id, email=email)
        if prev and isinstance(prev.get("evidencePack"), dict):
            ep = prev["evidencePack"]
            return {
                "evidences": list(ep.get("evidences") or []),
                "count": int(ep.get("count") or len(ep.get("evidences") or [])),
            }

    return {"evidences": [], "count": 0}


async def run_compose(
    roles_raw: Any = None,
    *,
    evidence_pack: Optional[dict[str, Any]] = None,
    pack_id: Optional[str] = None,
    evidences: Optional[list[Any]] = None,
    evidence_ids_allowed: Optional[list[Any]] = None,
    category: str = "hiring_insight",
    ai: Optional[dict[str, Any]] = None,
    use_workbench_llm: bool = True,
    workbench_llm: Any = None,
    workbench_model: str = "",
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    edition: Any = None,
    persist: bool = True,
    min_selected: int = 0,
) -> dict[str, Any]:
    """Compose journal cards from an evidence pack (LLM or cached fallback)."""
    cat = get_category(category)
    roles = parse_roles(roles_raw, category=cat["id"])
    ai = ai or {}
    has_key = bool(str(ai.get("apiKey") or ai.get("api_key") or "").strip())
    want_ai = bool(workbench_llm) or has_key or use_workbench_llm
    hist_kw = {"user_id": user_id, "email": email, "edition": edition}

    pack = await _resolve_evidence_pack(
        evidence_pack=evidence_pack,
        pack_id=pack_id,
        evidences=evidences,
        user_id=user_id,
        email=email,
    )
    pack = _apply_evidence_selection(
        pack, evidences=evidences, evidence_ids_allowed=evidence_ids_allowed
    )
    selected = selected_evidences(pack)
    if min_selected and len(selected) < min_selected:
        ed = format_edition(edition, user_id=user_id, email=email)
        return {
            "ok": False,
            "error": f"选中证据不足（需至少 {min_selected} 条，当前 {len(selected)} 条）",
            "evidencePack": pack,
            "roles": roles,
            "category": cat["id"],
            "mode": "journal",
            "snippetCount": pack.get("count") or 0,
            "sources": [],
            "cover": {"title": cat["default_title"], "edition": ed},
            "edition": ed,
            "knowledge": [],
            "persisted": "none",
        }

    # Always attempt compose_with_llm; credentials come from ai / workbench_llm.
    # On failure → build_cards from evidence texts, mode cached, keep pack.
    try:
        gen = await compose_with_llm(
            roles,
            evidence_pack=pack,
            ai=ai if has_key else None,
            workbench_llm=workbench_llm if (want_ai and not has_key) else None,
            workbench_model=workbench_model,
            category=cat["id"],
            edition=edition,
            user_id=user_id,
            email=email,
        )
        payload: dict[str, Any] = {
            **gen,
            "ok": True,
            "mode": "journal",
            "category": cat["id"],
            "roles": roles,
        }
    except Exception as llm_err:  # noqa: BLE001
        texts = [str(e.get("text") or "") for e in selected if e.get("text")]
        payload = build_cards(roles, [texts], category=cat["id"], **hist_kw)
        payload["ok"] = True
        payload["mode"] = "cached"
        payload["llmError"] = str(llm_err)
        payload["roles"] = roles
        for card in payload.get("knowledge") or []:
            if not isinstance(card, dict):
                continue
            card_text = " ".join(
                str(x or "")
                for x in (card.get("topicTitle"), card.get("concept"), card.get("keyPoint"))
            )
            eids = validate_evidence_ids([], pack, card_text=card_text)
            card["evidenceIds"] = eids
            card["stance"] = "evidence" if eids else "opinion"

    ed = format_edition(edition, user_id=user_id, email=email)
    cover = payload.get("cover") if isinstance(payload.get("cover"), dict) else {}
    cover = dict(cover)
    cover["edition"] = ed
    payload["cover"] = cover
    payload["edition"] = ed
    payload["category"] = cat["id"]
    payload["evidencePack"] = pack
    payload["snippetCount"] = int(pack.get("count") or 0)
    if not payload.get("sources"):
        payload["sources"] = [e.get("text") for e in selected[:6] if e.get("text")]

    from cn_social_agent.action_errors import journal_quality_items
    from cn_social_agent.cards.quality import journal_depth_report

    depth = journal_depth_report(
        payload,
        rich_journal=bool(payload.get("frontMatter")) or len(payload.get("knowledge") or []) >= 4,
    )
    payload["depth"] = depth
    payload["quality_items"] = journal_quality_items(depth)
    payload["quality_gate_pass"] = bool(depth.get("ok")) and payload.get("mode") != "cached"
    if not depth.get("ok"):
        payload["quality_hint"] = depth.get("hint") or "成刊未达标"
    elif payload.get("mode") == "cached":
        payload["quality_hint"] = "成刊已降级为模板，不建议直接导出"
        payload["quality_gate_pass"] = False
    else:
        payload["quality_hint"] = depth.get("hint") or "成刊质检通过"

    if persist:
        rec = {
            "roles": roles,
            "category": cat["id"],
            "cover": cover,
            "knowledge": payload.get("knowledge"),
            "sources": payload.get("sources") or [],
            "mode": payload.get("mode") or "journal",
            "snippetCount": payload.get("snippetCount") or 0,
            "edition": ed,
            "evidencePack": pack,
            "ok": payload.get("ok", True),
            "depth": depth,
            "quality_gate_pass": payload.get("quality_gate_pass"),
            "quality_hint": payload.get("quality_hint") or "",
        }
        if payload.get("frontMatter") is not None:
            rec["frontMatter"] = payload["frontMatter"]
        if payload.get("llmError"):
            rec["llmError"] = payload["llmError"]
        if pack_id:
            rec["id"] = str(pack_id)
        saved = save_history_record(rec, user_id=user_id, email=email)
        payload["id"] = saved["id"]
        payload["packId"] = saved["id"]
        try:
            from cn_social_agent.cards.cloud import upsert_card_record

            ok = await upsert_card_record(saved, user_id=user_id, email=email)
            payload["persisted"] = "insforge" if ok else "local"
        except Exception:  # noqa: BLE001
            payload["persisted"] = "local"
    else:
        payload["persisted"] = "none"

    return payload


async def run_scan(
    roles_raw: Any,
    *,
    category: str = "hiring_insight",
    ai: Optional[dict[str, Any]] = None,
    use_workbench_llm: bool = True,
    workbench_llm: Any = None,
    workbench_model: str = "",
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    edition: Any = None,
) -> dict[str, Any]:
    """Shallow research (no history) + compose (persist once). Mode ``ai`` when LLM ok."""
    researched = await run_research(
        roles_raw,
        category=category,
        depth="shallow",
        persist=False,
        user_id=user_id,
        email=email,
        edition=edition,
    )
    pack = researched.get("evidencePack") or {"evidences": [], "count": 0}
    composed = await run_compose(
        roles_raw,
        evidence_pack=pack,
        category=category,
        ai=ai,
        use_workbench_llm=use_workbench_llm,
        workbench_llm=workbench_llm,
        workbench_model=workbench_model,
        user_id=user_id,
        email=email,
        edition=edition,
        persist=True,
        min_selected=0,
    )
    if composed.get("mode") == "journal":
        composed["mode"] = "ai"
    return composed
