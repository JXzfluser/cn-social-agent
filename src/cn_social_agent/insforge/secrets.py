from __future__ import annotations

from typing import Any, Optional

from .client import InsForgeClient, InsForgeError


class InsForgeSecrets:
    """InsForge Secrets API wrapper.

    Maps to InsForge secret endpoints:
      GET    /api/secrets       - list secret metadata
      POST   /api/secrets       - create secret
      GET    /api/secrets/:key  - get secret value
      PUT    /api/secrets/:key  - update secret
      DELETE /api/secrets/:key  - delete secret
    """

    def __init__(self, client: InsForgeClient):
        self._client = client

    async def list_secrets(self) -> list[dict[str, Any]]:
        result = await self._client.api_get("/api/secrets")
        return result.get("secrets", [])

    async def get_secret(self, key: str) -> Optional[str]:
        try:
            result = await self._client.api_get(f"/api/secrets/{key}")
            return result.get("value", "")
        except InsForgeError:
            return None

    async def create_secret(self, key: str, value: str) -> dict[str, Any]:
        return await self._client.api_post("/api/secrets", json_body={"key": key, "value": value})

    async def update_secret(self, key: str, value: str) -> Optional[dict[str, Any]]:
        try:
            return await self._client.api_put(f"/api/secrets/{key}", json_body={"value": value})
        except InsForgeError:
            return None

    async def delete_secret(self, key: str) -> None:
        await self._client.api_delete(f"/api/secrets/{key}")
