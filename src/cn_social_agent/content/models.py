"""Normalize Content Project records."""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from cn_social_agent.cards.topic import build_search_terms, extract_short_topic
from cn_social_agent.content.board import BOARD_STATUSES, project_lane

STATUSES = BOARD_STATUSES


def new_project_id() -> str:
    return f"cp_{uuid.uuid4().hex[:16]}"


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_project(
    raw: dict[str, Any] | None,
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> dict[str, Any]:
    """Fill defaults and distill short_topic / search_terms."""
    src = dict(raw or {})
    topic = str(src.get("topic") or "").strip()
    notes = str(src.get("research_notes") or "").strip()
    short = str(src.get("short_topic") or "").strip() or extract_short_topic(topic, notes)
    if not short and topic:
        short = topic[:40]
    terms = src.get("search_terms")
    if not isinstance(terms, list) or not terms:
        terms = build_search_terms(topic or short, notes) if (topic or short) else []
    else:
        terms = [str(t).strip() for t in terms if str(t or "").strip()][:8]

    source = src.get("source") if isinstance(src.get("source"), dict) else {}
    kind = str(source.get("kind") or src.get("source_kind") or "manual").strip() or "manual"
    if kind not in ("hotspot", "url", "manual", "agent"):
        kind = "manual"
    source_out = {
        "kind": kind,
        "url": str(source.get("url") or src.get("url") or "")[:500],
        "title": str(source.get("title") or src.get("source_title") or "")[:200],
        "name": str(source.get("name") or src.get("source") or "")[:80],
    }

    evidence = src.get("evidence_pack") or src.get("evidencePack")
    if not isinstance(evidence, dict):
        evidence = {"evidences": [], "count": 0}
    else:
        evs = list(evidence.get("evidences") or [])
        evidence = {"evidences": evs, "count": int(evidence.get("count") or len(evs))}

    artifacts = src.get("artifacts") if isinstance(src.get("artifacts"), dict) else {}
    artifacts_out = {
        "journal_id": artifacts.get("journal_id") or None,
        "video_id": artifacts.get("video_id") or None,
        "presentation_id": artifacts.get("presentation_id") or None,
    }

    status = str(src.get("status") or "researching").strip()
    if status not in STATUSES:
        status = "researching"

    canvas = src.get("canvas") if isinstance(src.get("canvas"), dict) else {}
    canvas_nodes = canvas.get("nodes")
    canvas_edges = canvas.get("edges")
    canvas_out = {
        "nodes": [n for n in canvas_nodes if isinstance(n, dict)][:200]
        if isinstance(canvas_nodes, list)
        else [],
        "edges": [e for e in canvas_edges if isinstance(e, dict)][:300]
        if isinstance(canvas_edges, list)
        else [],
        "updated_at": str(canvas.get("updated_at") or ""),
    }

    pid = str(src.get("id") or "").strip() or new_project_id()
    now = _iso_now()
    quality = src.get("quality") if isinstance(src.get("quality"), dict) else {"items": [], "blockers": []}
    out = {
        "id": pid,
        "user_id": str(user_id or src.get("user_id") or "").strip(),
        "email": str(email or src.get("email") or "").strip().lower(),
        "topic": topic or short,
        "short_topic": short,
        "category": str(src.get("category") or "").strip(),
        "source": source_out,
        "research_notes": notes[:8000],
        "search_terms": terms,
        "evidence_pack": evidence,
        "quality": quality,
        "artifacts": artifacts_out,
        "canvas": canvas_out,
        "status": status,
        "why": str(src.get("why") or "")[:500],
        "topic_key": str(src.get("topic_key") or "")[:120],
        "created_at": str(src.get("created_at") or now),
        "updated_at": now,
        "ts": str(src.get("ts") or now),
    }
    out["lane"] = project_lane(out)
    return out
