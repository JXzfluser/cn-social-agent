"""Card export image storage for publish."""

from __future__ import annotations

import re
from pathlib import Path


def exports_dir() -> Path:
    root = Path(__file__).resolve().parents[4]
    d = root / "data" / "cards" / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_id(history_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", (history_id or "").strip())[:80] or "anon"


def export_item_dir(history_id: str) -> Path:
    d = exports_dir() / _safe_id(history_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_export_images(history_id: str) -> list[Path]:
    d = export_item_dir(history_id)
    files = sorted(d.glob("*.png"), key=lambda p: p.name)
    return files


def save_uploaded_images(history_id: str, files: list[tuple[str, bytes]]) -> list[Path]:
    """Save (filename, bytes) under export dir; returns paths in order."""
    d = export_item_dir(history_id)
    # clear old pngs
    for old in d.glob("*.png"):
        old.unlink()
    out: list[Path] = []
    for i, (name, raw) in enumerate(files):
        safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name or f"{i:02d}.png")
        if not safe.lower().endswith(".png"):
            safe = f"{i:02d}_{safe}.png"
        path = d / f"{i:02d}_{safe}"
        path.write_bytes(raw)
        out.append(path)
    return out
