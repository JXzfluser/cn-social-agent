"""InsForge mirror for Idea Engine materials/cards (`wb_idea_*`).

The engine keeps hot state in memory; this module best-effort persists it so
materials and card decisions (select/reject/feedback) survive restarts.
All operations degrade silently when no DB is wired.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from cn_social_agent.idea_engine.connectors.base import RawMaterial
from cn_social_agent.idea_engine.processor import IdeaCard

MATERIALS_TABLE = "wb_idea_materials"
CARDS_TABLE = "wb_idea_cards"

_db: Any = None


def set_idea_db(db: Any) -> None:
    global _db
    _db = db


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _parse_dt(v: Any) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v.replace(tzinfo=None) if v.tzinfo else v
    s = str(v or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except Exception:  # noqa: BLE001
        return None


def _material_row(m: RawMaterial, user_id: str) -> dict[str, Any]:
    return {
        "id": m.id,
        "user_id": user_id,
        "connector_id": (m.connector_id or "")[:60],
        "source": (m.source or "")[:60],
        "title": (m.title or "")[:300],
        "url": (m.url or "")[:1000],
        "summary": (m.summary or "")[:4000],
        "tags": [str(t) for t in (m.tags or [])][:20],
        "heat": int(m.heat or 0),
        "created_at": _iso(m.created_at),
    }


def _card_row(c: IdeaCard) -> dict[str, Any]:
    return {
        "id": c.id,
        "material_id": c.material_id,
        "user_id": c.user_id,
        "title": (c.title or "")[:200],
        "hook": (c.hook or "")[:2000],
        "angles": [str(a) for a in (c.angles or [])][:10],
        "heat_score": int(c.heat_score or 0),
        "difficulty_score": int(c.difficulty_score or 0),
        "time_window": (c.time_window or "")[:20],
        "content_type": (c.content_type or "technical")[:40],
        "status": (c.status or "pending")[:20],
        "feedback": c.feedback,
        "project_id": c.project_id,
        "created_at": _iso(c.created_at),
        "selected_at": _iso(c.selected_at),
        "rejected_at": _iso(c.rejected_at),
    }


def _material_from_row(row: dict[str, Any]) -> Optional[RawMaterial]:
    mid = str(row.get("id") or "").strip()
    if not mid:
        return None
    tags = row.get("tags")
    return RawMaterial(
        id=mid,
        connector_id=str(row.get("connector_id") or ""),
        source=str(row.get("source") or ""),
        title=str(row.get("title") or ""),
        url=str(row.get("url") or "") or None,
        summary=str(row.get("summary") or "") or None,
        tags=[t for t in tags if isinstance(t, str)] if isinstance(tags, list) else [],
        heat=int(row.get("heat") or 0),
        created_at=_parse_dt(row.get("created_at")) or datetime.now(),
    )


def _card_from_row(row: dict[str, Any]) -> Optional[IdeaCard]:
    cid = str(row.get("id") or "").strip()
    if not cid:
        return None
    angles = row.get("angles")
    return IdeaCard(
        id=cid,
        material_id=str(row.get("material_id") or ""),
        user_id=str(row.get("user_id") or ""),
        title=str(row.get("title") or ""),
        hook=str(row.get("hook") or ""),
        angles=[a for a in angles if isinstance(a, str)] if isinstance(angles, list) else [],
        heat_score=int(row.get("heat_score") or 0),
        difficulty_score=int(row.get("difficulty_score") or 0),
        time_window=str(row.get("time_window") or "48h"),
        content_type=str(row.get("content_type") or "technical"),
        status=str(row.get("status") or "pending"),
        feedback=row.get("feedback"),
        project_id=row.get("project_id"),
        created_at=_parse_dt(row.get("created_at")) or datetime.now(),
        selected_at=_parse_dt(row.get("selected_at")),
        rejected_at=_parse_dt(row.get("rejected_at")),
    )


async def _upsert(table: str, row: dict[str, Any]) -> bool:
    db = _db
    if db is None or not row.get("id"):
        return False
    try:
        existing = await db.query(table, filters={"id": f"eq.{row['id']}"}, limit=1)
        if existing:
            await db.update(table, {"id": f"eq.{row['id']}"}, row)
        else:
            await db.create(table, row)
        return True
    except Exception:  # noqa: BLE001
        return False


async def upsert_material(m: RawMaterial, user_id: str) -> bool:
    return await _upsert(MATERIALS_TABLE, _material_row(m, user_id))


async def upsert_card(c: IdeaCard) -> bool:
    return await _upsert(CARDS_TABLE, _card_row(c))


async def patch_card(card_id: str, fields: dict[str, Any]) -> bool:
    db = _db
    if db is None or not card_id or not fields:
        return False
    try:
        await db.update(CARDS_TABLE, {"id": f"eq.{card_id}"}, fields)
        return True
    except Exception:  # noqa: BLE001
        return False


async def load_materials(user_id: str, *, limit: int = 500) -> list[RawMaterial]:
    db = _db
    if db is None or not user_id:
        return []
    try:
        rows = await db.query(
            MATERIALS_TABLE, filters={"user_id": f"eq.{user_id}"}, limit=max(1, limit)
        )
    except Exception:  # noqa: BLE001
        return []
    out = []
    for row in rows or []:
        m = _material_from_row(row)
        if m:
            out.append(m)
    return out


async def load_cards(user_id: str, *, limit: int = 500) -> list[IdeaCard]:
    db = _db
    if db is None or not user_id:
        return []
    try:
        rows = await db.query(
            CARDS_TABLE, filters={"user_id": f"eq.{user_id}"}, limit=max(1, limit)
        )
    except Exception:  # noqa: BLE001
        return []
    out = []
    for row in rows or []:
        c = _card_from_row(row)
        if c:
            out.append(c)
    return out
