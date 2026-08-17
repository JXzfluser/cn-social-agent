from __future__ import annotations

from typing import Any

from .client import InsForgeClient


class InsForgeEmail:
    """InsForge Email API wrapper.

    Maps to InsForge email endpoints:
      POST /api/email/send-raw  - send a raw email
    """

    def __init__(self, client: InsForgeClient):
        self._client = client

    async def send_raw(self, to: str, subject: str, body: str) -> dict[str, Any]:
        return await self._client.api_post(
            "/api/email/send-raw",
            json_body={"to": to, "subject": subject, "body": body},
        )
