"""Video publisher protocol (separate from card image publishers)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, TypedDict


class VideoPublishResult(TypedDict, total=False):
    platform: str
    status: str  # draft | published | failed | skipped
    external_id: str
    url: str
    message: str
    clipboard: dict[str, Any]


class VideoPublisher(Protocol):
    name: str

    async def status(self, *, user_id: str) -> dict[str, Any]: ...

    async def publish_video(
        self,
        *,
        user_id: str,
        title: str,
        video_path: Path,
        hashtags: list[str],
        description: str,
        meta: dict[str, Any],
    ) -> VideoPublishResult: ...
