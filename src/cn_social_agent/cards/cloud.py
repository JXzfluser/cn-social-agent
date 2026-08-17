"""Persist knowledge card history to InsForge (`wb_card_history`)."""

from __future__ import annotations

from typing import Any, Optional

from cn_social_agent.cards.history import history_owner_key

TABLE = "wb_card_history"

# Optional InsForge DB set by AppState
_db: Any = None


def set_card_db(db: Any) -> None:
    global _db
    _db = db


def get_card_db() -> Any:
    return _db


def _row_from_rec(
    rec: dict[str, Any], *, user_id: Optional[str], email: Optional[str]
) -> dict[str, Any]:
    cover = rec.get("cover") if isinstance(rec.get("cover"), dict) else {}
    owner = history_owner_key(user_id=user_id, email=email)
    pack = rec.get("evidencePack")
    if not isinstance(pack, dict):
        pack = {}
    return {
        "user_id": (user_id or "").strip(),
        "email": (email or "").strip().lower(),
        "owner_key": owner,
        "card_id": str(rec.get("id") or ""),
        "edition": str(cover.get("edition") or rec.get("edition") or ""),
        "category": str(rec.get("category") or ""),
        "mode": str(rec.get("mode") or ""),
        "title": str(cover.get("title") or ""),
        "payload": rec,
        # Best-effort top-level column (schemas that have it)
        "evidence_pack": pack,
    }


def _is_evidence_pack_column_error(exc: BaseException) -> bool:
    """True when InsForge/PostgREST rejects unknown/missing evidence_pack column."""
    msg = str(exc).lower()
    if "evidence_pack" not in msg:
        return False
    markers = (
        "unknown",
        "missing",
        "does not exist",
        "could not find",
        "not found",
        "schema cache",
        "column",
        "pgrst",
        "42703",  # undefined_column
    )
    return any(m in msg for m in markers)


def _hydrate_evidence_pack(rec: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """Ensure evidencePack is present when payload or top-level column has it."""
    if isinstance(rec.get("evidencePack"), dict):
        return rec
    ep = row.get("evidence_pack")
    if isinstance(ep, dict):
        out = dict(rec)
        out["evidencePack"] = ep
        return out
    return rec


def _record_from_row(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    payload = row.get("payload")
    if isinstance(payload, dict) and payload.get("id"):
        return _hydrate_evidence_pack(payload, row)
    if row.get("card_id"):
        rec: dict[str, Any] = {
            "id": row.get("card_id"),
            "edition": row.get("edition"),
            "category": row.get("category"),
            "mode": row.get("mode"),
            "cover": {"title": row.get("title"), "edition": row.get("edition")},
            "knowledge": [],
        }
        return _hydrate_evidence_pack(rec, row)
    return None


async def _write_row(db: Any, row: dict[str, Any]) -> None:
    existing = await db.query(
        TABLE,
        filters={
            "owner_key": f"eq.{row['owner_key']}",
            "card_id": f"eq.{row['card_id']}",
        },
        limit=1,
    )
    if existing:
        rid = existing[0].get("id")
        await db.update(TABLE, {"id": f"eq.{rid}"}, row)
    else:
        await db.create(TABLE, row)


async def upsert_card_record(
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
        await _write_row(db, row)
        return True
    except Exception as exc:  # noqa: BLE001
        if "evidence_pack" in row and _is_evidence_pack_column_error(exc):
            stripped = {k: v for k, v in row.items() if k != "evidence_pack"}
            try:
                await _write_row(db, stripped)
                return True
            except Exception as exc2:  # noqa: BLE001
                print(f"[cards] InsForge upsert failed: {exc2}")
                return False
        print(f"[cards] InsForge upsert failed: {exc}")
        return False


async def list_card_records(
    *, user_id: Optional[str] = None, email: Optional[str] = None, limit: int = 100
) -> list[dict[str, Any]]:
    db = _db
    if db is None:
        return []
    owner = history_owner_key(user_id=user_id, email=email)
    try:
        rows = await db.query(
            TABLE,
            filters={"owner_key": f"eq.{owner}"},
            order="created_at.desc",
            limit=limit,
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            rec = _record_from_row(r)
            if rec:
                out.append(rec)
        return out
    except Exception as exc:  # noqa: BLE001
        print(f"[cards] InsForge list failed: {exc}")
        return []


async def get_card_record(
    card_id: str, *, user_id: Optional[str] = None, email: Optional[str] = None
) -> Optional[dict[str, Any]]:
    db = _db
    if db is None or not card_id:
        return None
    owner = history_owner_key(user_id=user_id, email=email)
    try:
        rows = await db.query(
            TABLE,
            filters={"owner_key": f"eq.{owner}", "card_id": f"eq.{card_id}"},
            limit=1,
        )
        if not rows:
            return None
        return _record_from_row(rows[0])
    except Exception as exc:  # noqa: BLE001
        print(f"[cards] InsForge get failed: {exc}")
        return None


async def delete_card_record(
    card_id: str, *, user_id: Optional[str] = None, email: Optional[str] = None
) -> bool:
    db = _db
    if db is None or not card_id:
        return False
    owner = history_owner_key(user_id=user_id, email=email)
    try:
        await db.delete(
            TABLE,
            filters={"owner_key": f"eq.{owner}", "card_id": f"eq.{card_id}"},
        )
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[cards] InsForge delete failed: {exc}")
        return False
