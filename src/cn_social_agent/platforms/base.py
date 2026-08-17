"""Platform publisher protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, TypedDict


class PublishResult(TypedDict):
    platform: str
    status: str  # draft | published | failed | skipped
    external_id: str
    url: str
    message: str


class PlatformPublisher(Protocol):
    name: str

    def auth_url(self, *, user_id: str, redirect_uri: str, state: str = "") -> str: ...

    async def handle_callback(
        self, *, user_id: str, query: dict[str, str]
    ) -> dict[str, Any]: ...

    async def status(self, *, user_id: str) -> dict[str, Any]: ...

    async def publish(
        self,
        *,
        user_id: str,
        title: str,
        image_paths: list[Path],
        direct: bool,
        meta: dict[str, Any],
    ) -> PublishResult: ...
