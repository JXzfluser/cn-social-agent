from __future__ import annotations

from typing import Any, Optional

from .client import InsForgeClient, InsForgeError


class InsForgeWebhooks:
    """InsForge Webhooks API wrapper.

    Maps to InsForge webhook endpoints:
      GET    /api/webhooks         - list webhooks
      POST   /api/webhooks         - create webhook
      GET    /api/webhooks/:id     - get webhook
      PUT    /api/webhooks/:id     - update webhook
      DELETE /api/webhooks/:id     - delete webhook
      POST   /api/webhooks/:id/trigger - test trigger
    """

    def __init__(self, client: InsForgeClient):
        self._client = client

    async def list_webhooks(self) -> list[dict[str, Any]]:
        return await self._client.api_get("/api/webhooks")

    async def get_webhook(self, webhook_id: str) -> Optional[dict[str, Any]]:
        try:
            return await self._client.api_get(f"/api/webhooks/{webhook_id}")
        except InsForgeError:
            return None

    async def create_webhook(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._client.api_post("/api/webhooks", json_body=data)

    async def update_webhook(self, webhook_id: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        try:
            return await self._client.api_put(f"/api/webhooks/{webhook_id}", json_body=data)
        except InsForgeError:
            return None

    async def delete_webhook(self, webhook_id: str) -> None:
        await self._client.api_delete(f"/api/webhooks/{webhook_id}")

    async def trigger(self, webhook_id: str, payload: Optional[dict] = None) -> dict[str, Any]:
        return await self._client.api_post(
            f"/api/webhooks/{webhook_id}/trigger",
            json_body=payload or {},
        )
