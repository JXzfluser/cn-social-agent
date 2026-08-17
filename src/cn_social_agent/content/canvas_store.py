"""Local JSON persistence for standalone canvas boards (per owner_key).

Project-bound canvases live inside the Content Project record. Standalone
boards used to sit in user prefs, which is memory-only in local mode and
column-whitelisted in InsForge mode — both lose data. They get their own file.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from cn_social_agent.content.canvas import normalize_canvas
from cn_social_agent.content.store_local import owner_key

MAX_BOARDS = 40
DEFAULT_BOARD_TITLE = "速记画布"


def new_board_id() -> str:
    return f"cv_{uuid.uuid4().hex[:10]}"


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def canvas_dir() -> Path:
    override = (os.getenv("CANVAS_BOARD_DIR") or "").strip()
    if override:
        d = Path(override)
    else:
        root = Path(__file__).resolve().parents[3]
        d = root / "data" / "canvas_boards"
    d.mkdir(parents=True, exist_ok=True)
    return d


def canvas_path(*, user_id: Optional[str] = None, email: Optional[str] = None) -> Path:
    return canvas_dir() / f"{owner_key(user_id=user_id, email=email)}.json"


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    return [b for b in data if isinstance(b, dict)] if isinstance(data, list) else []


def _write(path: Path, boards: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(boards[:MAX_BOARDS], ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _shape(raw: dict[str, Any]) -> dict[str, Any]:
    board_id = str(raw.get("id") or "").strip() or new_board_id()
    canvas = normalize_canvas(raw, board_id=board_id)
    canvas["title"] = canvas["title"] or DEFAULT_BOARD_TITLE
    canvas["created_at"] = str(raw.get("created_at") or canvas["updated_at"])
    return canvas


def list_boards(
    *, user_id: Optional[str] = None, email: Optional[str] = None
) -> list[dict[str, Any]]:
    rows = [_shape(b) for b in _read(canvas_path(user_id=user_id, email=email))]
    rows.sort(key=lambda b: str(b.get("updated_at") or ""), reverse=True)
    return rows


def get_board(
    board_id: str, *, user_id: Optional[str] = None, email: Optional[str] = None
) -> Optional[dict[str, Any]]:
    bid = str(board_id or "").strip()
    if not bid:
        return None
    for board in list_boards(user_id=user_id, email=email):
        if board["board_id"] == bid:
            return board
    return None


def save_board(
    board: dict[str, Any], *, user_id: Optional[str] = None, email: Optional[str] = None
) -> dict[str, Any]:
    shaped = _shape(dict(board or {}))
    path = canvas_path(user_id=user_id, email=email)
    rows = _read(path)
    out: list[dict[str, Any]] = []
    found = False
    for row in rows:
        if str(row.get("id") or row.get("board_id") or "") == shaped["board_id"]:
            out.append({**shaped, "id": shaped["board_id"]})
            found = True
        else:
            out.append(row)
    if not found:
        out.insert(0, {**shaped, "id": shaped["board_id"]})
    _write(path, out)
    return shaped


def delete_board(
    board_id: str, *, user_id: Optional[str] = None, email: Optional[str] = None
) -> bool:
    bid = str(board_id or "").strip()
    path = canvas_path(user_id=user_id, email=email)
    rows = _read(path)
    keep = [r for r in rows if str(r.get("id") or r.get("board_id") or "") != bid]
    if len(keep) == len(rows):
        return False
    _write(path, keep)
    return True


def ensure_default_board(
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    legacy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """First board for this owner, migrating the legacy prefs scratch canvas once."""
    boards = list_boards(user_id=user_id, email=email)
    if boards:
        return boards[0]
    seed = dict(legacy or {})
    seed.setdefault("title", DEFAULT_BOARD_TITLE)
    seed["id"] = new_board_id()
    return save_board(seed, user_id=user_id, email=email)
