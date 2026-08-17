"""Mock publisher for local / CI without platform credentials."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from cn_social_agent.platforms.base import PublishResult


class MockPublisher:
    name = "mock"

    def auth_url(self, *, user_id: str, redirect_uri: str, state: str = "") -> str:
        sep = "&" if "?" in redirect_uri else "?"
        return f"{redirect_uri}{sep}code=mock&state={state}&user_id={user_id}"

    async def handle_callback(
        self, *, user_id: str, query: dict[str, str]
    ) -> dict[str, Any]:
        return {"ok": True, "account": "mock-account", "user_id": user_id}

    async def status(self, *, user_id: str) -> dict[str, Any]:
        return {
            "platform": "mock",
            "ready": True,
            "authorized": True,
            "account": "mock-account",
            "message": "本地 Mock 平台",
        }

    async def publish(
        self,
        *,
        user_id: str,
        title: str,
        image_paths: list[Path],
        direct: bool,
        meta: dict[str, Any],
    ) -> PublishResult:
        eid = f"mock_{uuid.uuid4().hex[:8]}"
        return {
            "platform": "mock",
            "status": "published" if direct else "draft",
            "external_id": eid,
            "url": "",
            "message": (
                f"mock {'已发布' if direct else '已写入草稿'} · "
                f"{len(image_paths)} 张图 · {title}"
            ),
        }
