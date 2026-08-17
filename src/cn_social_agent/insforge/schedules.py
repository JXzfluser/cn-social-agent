from __future__ import annotations

from typing import Any, Optional

from .client import InsForgeClient, InsForgeError


class InsForgeSchedules:
    """InsForge Schedules API wrapper.

    Maps to InsForge schedule endpoints:
      GET    /api/schedules          - list schedules
      POST   /api/schedules          - create schedule
      GET    /api/schedules/config   - get config
      PATCH  /api/schedules/config   - update config
      GET    /api/schedules/:id      - get schedule by id
      PUT    /api/schedules/:id      - update schedule
      DELETE /api/schedules/:id      - delete schedule
    """

    def __init__(self, client: InsForgeClient):
        self._client = client

    async def list_schedules(self) -> list[dict[str, Any]]:
        return await self._client.api_get("/api/schedules")

    async def get_schedule(self, schedule_id: str) -> Optional[dict[str, Any]]:
        try:
            return await self._client.api_get(f"/api/schedules/{schedule_id}")
        except InsForgeError:
            return None

    async def create_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._client.api_post("/api/schedules", json_body=data)

    async def update_schedule(self, schedule_id: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        try:
            return await self._client.api_put(f"/api/schedules/{schedule_id}", json_body=data)
        except InsForgeError:
            return None

    async def delete_schedule(self, schedule_id: str) -> None:
        await self._client.api_delete(f"/api/schedules/{schedule_id}")

    async def get_config(self) -> dict[str, Any]:
        return await self._client.api_get("/api/schedules/config")

    async def update_config(self, retention_days: int) -> dict[str, Any]:
        return await self._client.api_patch(
            "/api/schedules/config",
            json_body={"retentionDays": retention_days},
        )
