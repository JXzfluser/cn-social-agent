from __future__ import annotations

from typing import Any, Optional

from .client import InsForgeClient


class InsForgeAnalytics:
    """InsForge Analytics API wrapper.

    Maps to InsForge analytics endpoints:
      GET /api/analytics/connection    - check analytics connection
      GET /api/analytics/dashboards    - list dashboards
      GET /api/analytics/query         - run analytics query
      GET /api/analytics/metrics       - get metrics
    """

    def __init__(self, client: InsForgeClient):
        self._client = client

    async def get_connection(self) -> dict[str, Any]:
        return await self._client.api_get("/api/analytics/connection")

    async def get_dashboards(self) -> list[dict[str, Any]]:
        return await self._client.api_get("/api/analytics/dashboards")

    async def query(self, metric: str, timeframe: str = "7d", **params) -> dict[str, Any]:
        query_params = {"metric": metric, "timeframe": timeframe, **params}
        return await self._client.api_get("/api/analytics/query", params=query_params)

    async def get_metrics(self, metric: Optional[str] = None) -> dict[str, Any]:
        params = {}
        if metric:
            params["metric"] = metric
        return await self._client.api_get("/api/analytics/metrics", params=params)
