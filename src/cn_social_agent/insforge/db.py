from __future__ import annotations

from typing import Any, Optional

from .client import InsForgeClient


class InsForgeDB:
    """InsForge Database API wrapper via PostgREST.

    Maps to PostgREST standard RESTful endpoints:
      GET    /{table}         - list/query records
      POST   /{table}         - create records
      PATCH  /{table}         - update records
      DELETE /{table}         - delete records
      GET    /{table}?id=eq.X - get single record
    """

    def __init__(self, client: InsForgeClient):
        self._client = client

    async def query(
        self,
        table: str,
        *,
        select: str = "*",
        filters: Optional[dict[str, str]] = None,
        order: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"select": select, "limit": limit, "offset": offset}
        if order:
            params["order"] = order
        if filters:
            for col, op_val in filters.items():
                params[col] = op_val

        return await self._client.api_get(
            f"/{table}",
            params=params,
            base="pgrst",
            use_auth=False,
        )

    async def get_by_id(
        self, table: str, id_value: str, id_column: str = "id", select: str = "*"
    ) -> Optional[dict[str, Any]]:
        results = await self.query(
            table,
            select=select,
            filters={f"{id_column}": f"eq.{id_value}"},
            limit=1,
        )
        if results:
            return results[0]
        return None

    async def create(
        self,
        table: str,
        data: dict[str, Any] | list[dict[str, Any]],
        *,
        prefer: str = "return=representation",
    ) -> list[dict[str, Any]]:
        # PostgREST accepts object or array; prefer array for consistent list responses.
        body = data if isinstance(data, list) else [data]
        resp = await self._client.api_request(
            "POST",
            f"/{table}",
            json_body=body,
            base="pgrst",
            use_auth=False,
            headers={"Prefer": prefer},
        )
        if resp.status_code in (200, 201):
            if not resp.content:
                return body
            parsed = resp.json()
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
            return body
        raise Exception(f"create failed ({resp.status_code}): {resp.text}")

    async def update(
        self,
        table: str,
        filters: dict[str, str],
        data: dict[str, Any],
        *,
        prefer: str = "return=representation",
    ) -> list[dict[str, Any]]:
        resp = await self._client.api_request(
            "PATCH",
            f"/{table}",
            json_body=data,
            base="pgrst",
            use_auth=False,
            params=filters,
            headers={"Prefer": prefer},
        )
        if resp.is_error:
            raise Exception(f"update failed: {resp.text}")
        return resp.json() if resp.content else []

    async def delete(
        self,
        table: str,
        filters: dict[str, str],
    ) -> None:
        resp = await self._client.api_request(
            "DELETE",
            f"/{table}",
            base="pgrst",
            use_auth=False,
            params=filters,
        )
        if resp.is_error:
            raise Exception(f"delete failed: {resp.text}")

    async def execute_sql(self, sql: str) -> Any:
        return await self._client.api_post(
            "/rpc/execute_sql",
            json_body={"sql": sql},
            base="pgrst",
            use_auth=False,
        )

    async def table_info(self, table: str) -> list[dict[str, Any]]:
        return await self.query(
            "information_schema.columns",
            filters={"table_name": f"eq.{table}"},
            select="column_name,data_type,is_nullable,column_default",
        )
