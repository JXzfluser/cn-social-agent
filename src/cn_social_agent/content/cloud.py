"""InsForge mirror for Content Projects (`wb_content_projects`)."""

from __future__ import annotations

from typing import Any, Optional

from cn_social_agent.content.models import normalize_project
from cn_social_agent.content.store_local import owner_key

TABLE = "wb_content_projects"

_db: Any = None


def set_content_db(db: Any) -> None:
    global _db
    _db = db


def get_content_db() -> Any:
    return _db


def _row_from_rec(
    rec: dict[str, Any], *, user_id: Optional[str], email: Optional[str]
) -> dict[str, Any]:
    owner = owner_key(user_id=user_id, email=email)
    return {
        "user_id": (user_id or "").strip(),
        "email": (email or "").strip().lower(),
        "owner_key": owner,
        "project_id": str(rec.get("id") or ""),
        "topic": str(rec.get("topic") or "")[:200],
        "short_topic": str(rec.get("short_topic") or "")[:80],
        "category": str(rec.get("category") or "")[:40],
        "status": str(rec.get("status") or "")[:24],
        "payload": rec,
    }


def _record_from_row(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    payload = row.get("payload")
    if isinstance(payload, dict) and payload.get("id"):
        return normalize_project(payload)
    if row.get("project_id"):
        return normalize_project(
            {
                "id": row.get("project_id"),
                "topic": row.get("topic"),
                "short_topic": row.get("short_topic"),
                "category": row.get("category"),
                "status": row.get("status"),
            }
        )
    return None


async def upsert_content_record(
    rec: dict[str, Any],
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> bool:
    db = _db
    if db is None or not rec.get("id"):
        return False
    row = _row_from_rec(rec, user_id=user_id, email=email)
    try:
        existing = await db.query(
            TABLE,
            filters={
                "owner_key": f"eq.{row['owner_key']}",
                "project_id": f"eq.{row['project_id']}",
            },
            limit=1,
        )
        if existing:
            rid = existing[0].get("id")
            await db.update(TABLE, {"id": f"eq.{rid}"}, row)
        else:
            await db.create(TABLE, row)
        return True
    except Exception:  # noqa: BLE001
        return False


async def get_content_record(
    project_id: str,
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    db = _db
    pid = str(project_id or "").strip()
    if db is None or not pid:
        return None
    owner = owner_key(user_id=user_id, email=email)
    try:
        rows = await db.query(
            TABLE,
            filters={"owner_key": f"eq.{owner}", "project_id": f"eq.{pid}"},
            limit=1,
        )
        if not rows:
            return None
        return _record_from_row(rows[0])
    except Exception:  # noqa: BLE001
        return None


async def list_content_records(
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    limit: int = 40,
) -> list[dict[str, Any]]:
    db = _db
    if db is None:
        return []
    owner = owner_key(user_id=user_id, email=email)
    try:
        rows = await db.query(
            TABLE,
            filters={"owner_key": f"eq.{owner}"},
            limit=max(1, min(100, int(limit or 40))),
        )
    except Exception:  # noqa: BLE001
        return []
    out: list[dict[str, Any]] = []
    for row in rows or []:
        rec = _record_from_row(row)
        if rec:
            out.append(rec)
    out.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    return out


async def delete_content_record(
    project_id: str,
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> bool:
    db = _db
    pid = str(project_id or "").strip()
    if db is None or not pid:
        return False
    owner = owner_key(user_id=user_id, email=email)
    try:
        rows = await db.query(
            TABLE,
            filters={"owner_key": f"eq.{owner}", "project_id": f"eq.{pid}"},
            limit=1,
        )
        if not rows:
            return False
        await db.delete(TABLE, {"id": f"eq.{rows[0].get('id')}"})
        return True
    except Exception:  # noqa: BLE001
        return False
