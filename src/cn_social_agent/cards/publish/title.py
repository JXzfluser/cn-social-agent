"""Publish title helpers."""

from __future__ import annotations

from typing import Any


def resolve_publish_title(cover: dict[str, Any] | None, *, max_len: int = 64) -> str:
    cover = cover or {}
    tags = cover.get("tags") if isinstance(cover.get("tags"), list) else []
    parts = [str(t).strip() for t in tags if str(t).strip()]
    title = " · ".join(parts) if parts else str(cover.get("title") or "").strip()
    title = title or "知识卡片"
    if len(title) <= max_len:
        return title
    return title[: max(0, max_len - 1)].rstrip(" ·") + "…"
