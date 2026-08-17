"""Persist card scan history under data/cards/ (stable per email / user)."""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from cn_social_agent.cards.themes import SERIES


def _safe_key(raw: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_@.+-]+", "_", (raw or "").strip().lower())[:96]
    return s or "anon"


def history_owner_key(*, user_id: Optional[str] = None, email: Optional[str] = None) -> str:
    """Prefer email so history survives memory-store user-id churn."""
    em = (email or "").strip().lower()
    if em:
        return "e_" + _safe_key(em.replace("@", "_at_"))
    return _safe_key(user_id or "anon")


def history_dir() -> Path:
    root = Path(__file__).resolve().parents[3]
    d = root / "data" / "cards"
    d.mkdir(parents=True, exist_ok=True)
    return d


def history_path(
    user_id: Optional[str] = None, *, email: Optional[str] = None
) -> Path:
    return history_dir() / f"{history_owner_key(user_id=user_id, email=email)}.json"


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return []


def _merge_rows(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for rows in groups:
        for r in rows:
            if not isinstance(r, dict):
                continue
            rid = str(r.get("id") or "")
            if rid and rid in seen:
                continue
            if rid:
                seen.add(rid)
            out.append(r)
    out.sort(key=lambda r: str(r.get("ts") or ""), reverse=True)
    return out[:100]


def _migrate_history(user_id: Optional[str], email: Optional[str]) -> None:
    """Consolidate orphaned per-uuid files into the stable owner file (once)."""
    path = history_path(user_id, email=email)
    existing = _read_rows(path)
    if existing:
        return

    d = history_dir()
    chunks: list[list[dict[str, Any]]] = []
    legacy = d / "history.json"
    chunks.append(_read_rows(legacy))

    # Prior file named by raw user_id (pre-email key)
    if user_id:
        chunks.append(_read_rows(d / f"{_safe_key(user_id)}.json"))

    em = (email or "").strip().lower()
    # Demo / local: recover all scattered u_*.json generations after memory restarts
    if em == "demo@local.test" or (user_id or "") == "u_demo_local":
        for f in sorted(d.glob("u_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            chunks.append(_read_rows(f))
    else:
        # Other users: only files that already reference this user_id
        uid = (user_id or "").strip()
        if uid:
            for f in d.glob("u_*.json"):
                rows = _read_rows(f)
                if any(str(r.get("user_id") or "") == uid for r in rows):
                    chunks.append(rows)

    merged = _merge_rows(*chunks)
    if merged:
        path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")


def load_history(
    user_id: Optional[str] = None, *, email: Optional[str] = None
) -> list[dict[str, Any]]:
    _migrate_history(user_id, email)
    path = history_path(user_id, email=email)
    rows = _read_rows(path)
    if rows:
        return rows
    # Fallback: legacy global file
    return _read_rows(history_dir() / "history.json")


def save_history_record(
    rec: dict[str, Any],
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> dict[str, Any]:
    _migrate_history(user_id, email)
    rows = load_history(user_id, email=email)
    if not rec.get("id"):
        rec["id"] = f"h{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    if not rec.get("ts"):
        rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if user_id:
        rec["user_id"] = user_id
    if email:
        rec["email"] = (email or "").strip().lower()
    # Preserve evidencePack when present (research / journal drafts)
    if "evidencePack" in rec and rec.get("evidencePack") is None:
        rec["evidencePack"] = {"evidences": [], "count": 0}
    # Dedupe id then prepend
    rid = str(rec.get("id"))
    rows = [r for r in rows if str(r.get("id")) != rid]
    rows.insert(0, rec)
    path = history_path(user_id, email=email)
    path.write_text(json.dumps(rows[:100], ensure_ascii=False, indent=2), encoding="utf-8")
    return rec


def list_history_summaries(
    user_id: Optional[str] = None, *, email: Optional[str] = None
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in load_history(user_id, email=email):
        cover = r.get("cover") or {}
        knowledge = r.get("knowledge") or []
        pubs = r.get("publish") if isinstance(r.get("publish"), list) else []
        out.append(
            {
                "id": r.get("id"),
                "ts": r.get("ts"),
                "title": cover.get("title") or "",
                "mode": r.get("mode") or "cached",
                "category": r.get("category") or "hiring_insight",
                "snippetCount": r.get("snippetCount") or 0,
                "topics": [k.get("topicTitle") or "" for k in knowledge if isinstance(k, dict)],
                "dateLabel": cover.get("edition") or cover.get("gradientPart") or "",
                "edition": cover.get("edition") or "",
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
    return out


def get_history_item(
    item_id: str, *, user_id: Optional[str] = None, email: Optional[str] = None
) -> dict[str, Any] | None:
    for r in load_history(user_id, email=email):
        if str(r.get("id")) == str(item_id):
            return r
    return None


def delete_history_item(
    item_id: str, *, user_id: Optional[str] = None, email: Optional[str] = None
) -> bool:
    rows = load_history(user_id, email=email)
    keep = [r for r in rows if str(r.get("id")) != str(item_id)]
    if len(keep) == len(rows):
        return False
    path = history_path(user_id, email=email)
    path.write_text(json.dumps(keep[:100], ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def append_publish_record(
    item_id: str,
    entry: dict[str, Any],
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> bool:
    """Append a publish result onto history item's `publish` list."""
    rows = load_history(user_id, email=email)
    found = False
    for r in rows:
        if str(r.get("id")) != str(item_id):
            continue
        found = True
        pubs = r.get("publish")
        if not isinstance(pubs, list):
            pubs = []
        row = dict(entry)
        if not row.get("ts"):
            row["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        pubs.append(row)
        r["publish"] = pubs[-20:]
        break
    if not found:
        return False
    path = history_path(user_id, email=email)
    path.write_text(json.dumps(rows[:100], ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def default_knowledge_pad() -> dict[str, Any]:
    from cn_social_agent.cards.themes import THEMES

    th = THEMES[0]
    return {
        **SERIES,
        "topicTitle": th["topicTitle"],
        "concept": th["concept"],
        "keyPoint": th["keyBase"],
        "realPoints": [],
        "example": th["example"],
        "flow": list(th.get("flow") or [])[:4],
    }
