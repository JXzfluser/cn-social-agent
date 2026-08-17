"""Local JSON persistence for Content Projects (per owner_key)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from cn_social_agent.content.models import normalize_project


def _safe_key(raw: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_@.+-]+", "_", (raw or "").strip().lower())[:96]
    return s or "anon"


def owner_key(*, user_id: Optional[str] = None, email: Optional[str] = None) -> str:
    em = (email or "").strip().lower()
    if em:
        return "e_" + _safe_key(em.replace("@", "_at_"))
    return _safe_key(user_id or "anon")


def projects_dir() -> Path:
    override = (os.getenv("CONTENT_PROJECT_DIR") or "").strip()
    if override:
        d = Path(override)
    else:
        root = Path(__file__).resolve().parents[3]
        d = root / "data" / "content_projects"
    d.mkdir(parents=True, exist_ok=True)
    return d


def projects_path(*, user_id: Optional[str] = None, email: Optional[str] = None) -> Path:
    return projects_dir() / f"{owner_key(user_id=user_id, email=email)}.json"


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return []


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows[:100], ensure_ascii=False, indent=2), encoding="utf-8")


def save_project(
    rec: dict[str, Any],
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> dict[str, Any]:
    p = normalize_project(rec, user_id=user_id, email=email)
    path = projects_path(user_id=user_id or p.get("user_id"), email=email or p.get("email"))
    rows = _read_rows(path)
    out: list[dict[str, Any]] = []
    found = False
    for r in rows:
        if str(r.get("id") or "") == p["id"]:
            out.append(p)
            found = True
        else:
            out.append(r)
    if not found:
        out.insert(0, p)
    out.sort(key=lambda r: str(r.get("updated_at") or r.get("ts") or ""), reverse=True)
    _write_rows(path, out)
    return p


def get_project(
    project_id: str,
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    pid = str(project_id or "").strip()
    if not pid:
        return None
    path = projects_path(user_id=user_id, email=email)
    for r in _read_rows(path):
        if str(r.get("id") or "") == pid:
            return normalize_project(r, user_id=user_id, email=email)
    return None


def list_projects(
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    limit: int = 40,
) -> list[dict[str, Any]]:
    path = projects_path(user_id=user_id, email=email)
    rows = [
        normalize_project(r, user_id=user_id, email=email)
        for r in _read_rows(path)
        if isinstance(r, dict)
    ]
    rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    return rows[: max(1, min(100, int(limit or 40)))]


def delete_project(
    project_id: str,
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> bool:
    pid = str(project_id or "").strip()
    path = projects_path(user_id=user_id, email=email)
    rows = _read_rows(path)
    keep = [r for r in rows if str(r.get("id") or "") != pid]
    if len(keep) == len(rows):
        return False
    _write_rows(path, keep)
    return True
