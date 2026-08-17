"""Content Project board lanes — candidate / active / export_ready (+ rejected)."""

from __future__ import annotations

import time
from typing import Any, Optional

# Board-facing lanes (UI columns). Internal status may be finer.
LANES = ("candidate", "active", "export_ready", "rejected")

LANE_LABELS: dict[str, str] = {
    "candidate": "候选",
    "active": "进行中",
    "export_ready": "可导出",
    "rejected": "已打回",
}

# Status values accepted on Content Project
BOARD_STATUSES = frozenset(
    {
        "candidate",
        "researching",
        "composing",
        "producing",
        "export_ready",
        "done",
        "rejected",
    }
)


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def project_lane(project: dict[str, Any] | None) -> str:
    """Map a project record to a board lane."""
    p = project or {}
    status = str(p.get("status") or "").strip()
    q = p.get("quality") if isinstance(p.get("quality"), dict) else {}
    if status == "rejected" or q.get("rejected"):
        return "rejected"
    if status == "export_ready" or status == "done" or q.get("export_ready"):
        return "export_ready"
    if status == "candidate":
        return "candidate"
    return "active"


def lane_to_status(lane: str, *, current_status: str = "") -> str:
    """Pick a concrete status when moving a card onto a lane."""
    lane = (lane or "").strip()
    if lane == "candidate":
        return "candidate"
    if lane == "export_ready":
        return "export_ready"
    if lane == "rejected":
        return "rejected"
    # active
    cur = (current_status or "").strip()
    if cur in ("researching", "composing", "producing"):
        return cur
    return "researching"


def apply_lane_move(
    project: dict[str, Any],
    lane: str,
    *,
    reason: str = "",
) -> dict[str, Any]:
    """Return patch fields to move a project onto a board lane."""
    lane = (lane or "").strip()
    if lane not in LANES:
        raise ValueError(f"unknown lane: {lane}")
    cur = dict(project or {})
    q = dict(cur.get("quality") if isinstance(cur.get("quality"), dict) else {})
    status = lane_to_status(lane, current_status=str(cur.get("status") or ""))

    if lane == "export_ready":
        q["export_ready"] = True
        q["gate_pass"] = bool(q.get("gate_pass", True))
        q["rejected"] = False
        q.pop("reject_reason", None)
        q["hint"] = str(q.get("hint") or "已标记可导出（不会自动发布）")[:200]
    elif lane == "rejected":
        reason = (reason or "").strip()
        if not reason:
            raise ValueError("打回需要填写理由")
        q["export_ready"] = False
        q["rejected"] = True
        q["reject_reason"] = reason[:500]
        q["rejected_at"] = _iso_now()
        q["hint"] = f"已打回：{reason[:80]}"
    else:
        # candidate or active — clear reject/export flags for a clean reopen
        q["export_ready"] = False
        q["rejected"] = False
        if reason:
            # optional note when promoting
            q["lane_note"] = reason[:200]
        if lane == "active" and q.get("reject_reason"):
            q["reopen_note"] = f"从打回复开 · 原理由：{q.get('reject_reason')}"[:240]

    return {"status": status, "quality": q}


def group_projects_by_lane(
    projects: list[dict[str, Any]],
    *,
    include_rejected: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {k: [] for k in LANES}
    for p in projects:
        lane = project_lane(p)
        if lane == "rejected" and not include_rejected:
            continue
        brief = board_card(p)
        out.setdefault(lane, []).append(brief)
    return out


def board_card(project: dict[str, Any]) -> dict[str, Any]:
    """Compact card payload for the board UI."""
    p = project or {}
    q = p.get("quality") if isinstance(p.get("quality"), dict) else {}
    pack = p.get("evidence_pack") if isinstance(p.get("evidence_pack"), dict) else {}
    arts = p.get("artifacts") if isinstance(p.get("artifacts"), dict) else {}
    source = p.get("source") if isinstance(p.get("source"), dict) else {}
    canvas = p.get("canvas") if isinstance(p.get("canvas"), dict) else {}
    nodes = canvas.get("nodes") if isinstance(canvas.get("nodes"), list) else []
    progress = project_progress(p)
    return {
        "id": p.get("id"),
        "topic": p.get("topic"),
        "short_topic": p.get("short_topic"),
        "category": p.get("category") or "",
        "status": p.get("status"),
        "lane": project_lane(p),
        "why": str(p.get("why") or "")[:200],
        "source_kind": source.get("kind") or "",
        "source_name": source.get("name") or "",
        "url": source.get("url") or "",
        "evidence_count": int(pack.get("count") or len(pack.get("evidences") or [])),
        "canvas_count": len(nodes),
        "journal_id": arts.get("journal_id") or "",
        "video_id": arts.get("video_id") or "",
        "presentation_id": arts.get("presentation_id") or "",
        "export_ready": bool(q.get("export_ready")),
        "reject_reason": str(q.get("reject_reason") or "")[:200],
        "hint": str(q.get("hint") or "")[:160],
        "updated_at": p.get("updated_at") or "",
        "created_at": p.get("created_at") or "",
        "progress": progress,
    }


def project_progress(project: dict[str, Any] | None) -> dict[str, Any]:
    """Summarize artifact / quality progress for cards and the detail drawer."""
    p = project or {}
    pack = p.get("evidence_pack") if isinstance(p.get("evidence_pack"), dict) else {}
    evidences = pack.get("evidences") if isinstance(pack.get("evidences"), list) else []
    evidence_count = int(pack.get("count") or len(evidences) or 0)
    canvas = p.get("canvas") if isinstance(p.get("canvas"), dict) else {}
    nodes = canvas.get("nodes") if isinstance(canvas.get("nodes"), list) else []
    arts = p.get("artifacts") if isinstance(p.get("artifacts"), dict) else {}
    q = p.get("quality") if isinstance(p.get("quality"), dict) else {}
    has_journal = bool(arts.get("journal_id"))
    has_presentation = bool(arts.get("presentation_id"))
    has_video = bool(arts.get("video_id"))
    has_canvas = bool(nodes) or int(p.get("canvas_count") or 0) > 0
    # Cards may already be compacted — fall back to their counts/ids.
    if "evidence_count" in p and not evidences:
        evidence_count = int(p.get("evidence_count") or 0)
    if "canvas_count" in p and not nodes:
        has_canvas = int(p.get("canvas_count") or 0) > 0
    if "journal_id" in p and not arts.get("journal_id"):
        has_journal = bool(p.get("journal_id"))
    if "presentation_id" in p and not arts.get("presentation_id"):
        has_presentation = bool(p.get("presentation_id"))
    if "video_id" in p and not arts.get("video_id"):
        has_video = bool(p.get("video_id"))
    export_ready = bool(q.get("export_ready") or p.get("export_ready"))
    return {
        "evidence": evidence_count,
        "canvas": has_canvas,
        "journal": has_journal,
        "presentation": has_presentation,
        "video": has_video,
        "export_ready": export_ready,
        "gate_pass": bool(q.get("gate_pass")),
        "rejected": bool(q.get("rejected") or p.get("status") == "rejected"),
        "markers": {
            "evidence": evidence_count > 0,
            "canvas": has_canvas,
            "journal": has_journal,
            "presentation": has_presentation,
            "video": has_video,
            "export_ready": export_ready,
        },
    }


def filter_projects(
    cards: list[dict[str, Any]],
    *,
    query: str = "",
    category: str = "",
    artifact: str = "",
) -> list[dict[str, Any]]:
    """Filter board cards by free-text query, category, and artifact presence."""
    q = (query or "").strip().lower()
    cat = (category or "").strip().lower()
    art = (artifact or "").strip().lower()
    out: list[dict[str, Any]] = []
    for card in cards:
        hay = " ".join(
            [
                str(card.get("topic") or ""),
                str(card.get("short_topic") or ""),
                str(card.get("source_name") or ""),
                str(card.get("source_kind") or ""),
                str(card.get("why") or ""),
            ]
        ).lower()
        if q and q not in hay:
            continue
        if cat and str(card.get("category") or "").strip().lower() != cat:
            continue
        progress = card.get("progress") if isinstance(card.get("progress"), dict) else project_progress(card)
        markers = progress.get("markers") if isinstance(progress.get("markers"), dict) else {}
        if art == "evidence" and not markers.get("evidence"):
            continue
        if art == "canvas" and not markers.get("canvas"):
            continue
        if art == "journal" and not markers.get("journal"):
            continue
        if art == "presentation" and not markers.get("presentation"):
            continue
        if art == "video" and not markers.get("video"):
            continue
        if art == "export_ready" and not markers.get("export_ready"):
            continue
        out.append(card)
    return out


def sort_projects(cards: list[dict[str, Any]], sort: str = "updated_desc") -> list[dict[str, Any]]:
    """Sort board cards. Unknown keys fall back to updated_desc."""
    key = (sort or "updated_desc").strip().lower()
    rows = list(cards)

    def _ts(value: Any) -> str:
        return str(value or "")

    if key == "evidence_desc":
        rows.sort(key=lambda c: int(c.get("evidence_count") or 0), reverse=True)
    elif key == "created_desc":
        rows.sort(key=lambda c: _ts(c.get("created_at")), reverse=True)
    elif key == "created_asc":
        rows.sort(key=lambda c: _ts(c.get("created_at")))
    elif key == "updated_asc":
        rows.sort(key=lambda c: _ts(c.get("updated_at")))
    else:
        rows.sort(key=lambda c: _ts(c.get("updated_at")), reverse=True)
    return rows


def collect_categories(cards: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for card in cards:
        cat = str(card.get("category") or "").strip()
        if cat and cat not in seen:
            seen.append(cat)
    return seen
