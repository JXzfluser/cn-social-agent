"""Tenant-scoped data access built on InsForge PostgREST.

This is the *only* sanctioned way for request-handling code to read or write
tenant data.

Why this exists
---------------
The legacy :class:`cn_social_agent.insforge.db.InsForgeDB` talks to PostgREST
directly on port 5434 with ``use_auth=False``. PostgREST then sees an anonymous
caller, so every row-level security policy collapses — isolation was being
enforced (or missed) purely by remembering to add ``user_id=eq.X`` filters in
application code. One forgotten filter and user A reads user B's data.

:class:`TenantDB` instead routes through the InsForge gateway at
``/api/database/records/*`` **with the end user's JWT**. The gateway verifies
the token and re-signs an internal token carrying ``sub = <user uuid>`` before
forwarding to PostgREST, so ``auth.uid()`` resolves to the real user and the
database enforces isolation itself.

Consequences that callers must internalise:

* Filters on ``user_id`` are defence in depth, not the primary control.
* Inserts must supply ``user_id`` (RLS ``WITH CHECK``) — done automatically.
* A missing tenant raises rather than degrading to a shared scope.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional, Sequence

from .tenant import require

logger = logging.getLogger(__name__)

# PostgREST comparison operators we are willing to pass through.
_SAFE_OPS = frozenset(
    {
        "eq",
        "neq",
        "gt",
        "gte",
        "lt",
        "lte",
        "like",
        "ilike",
        "is",
        "in",
        "cs",
        "cd",
        "ov",
        "sl",
        "sr",
        "nxl",
        "nxr",
        "adj",
    }
)


class RlsViolation(RuntimeError):
    """Raised when the database rejects an operation under RLS."""


class TenantDB:
    """RLS-aware, tenant-bound PostgREST client."""

    def __init__(self, client: Any) -> None:
        self._client = client

    # ── internals ────────────────────────────────────────────────

    @staticmethod
    def _records_path(table: str) -> str:
        return f"/api/database/records/{table}"

    def _headers(self, prefer: Optional[str] = None) -> dict[str, str]:
        tenant = require()
        headers = {"Authorization": f"Bearer {tenant.token}"}
        if prefer:
            headers["Prefer"] = prefer
        return headers

    async def _request(
        self,
        method: str,
        table: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Any = None,
        prefer: Optional[str] = None,
    ) -> Any:
        resp = await self._client.api_request(
            method,
            self._records_path(table),
            json_body=json_body,
            params=params,
            headers=self._headers(prefer),
            base="api",
            # Critical: never let the client inject its cached admin token.
            use_auth=False,
        )
        if resp.status_code in (401, 403):
            raise RlsViolation(
                f"{method} {table} rejected by RLS/auth ({resp.status_code}): {resp.text}"
            )
        if resp.is_error:
            raise RlsViolation(f"{method} {table} failed ({resp.status_code}): {resp.text}")
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    @staticmethod
    def _build_params(
        select: str,
        filters: Optional[dict[str, str]],
        order: Optional[str],
        limit: Optional[int],
        offset: Optional[int],
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"select": select}
        for key, value in (filters or {}).items():
            if "." in key:
                op = key.rsplit(".", 1)[1]
                if op not in _SAFE_OPS:
                    raise ValueError(f"unsupported filter operator: {op}")
            params[key] = value
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        return params

    # ── reads ────────────────────────────────────────────────────

    async def query(
        self,
        table: str,
        *,
        select: str = "*",
        filters: Optional[dict[str, str]] = None,
        order: Optional[str] = None,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
    ) -> list[dict[str, Any]]:
        """List rows visible to the current tenant (RLS-scoped)."""
        params = self._build_params(select, filters, order, limit, offset)
        data = await self._request("GET", table, params=params)
        if data is None:
            return []
        return data if isinstance(data, list) else [data]

    async def get_by_id(
        self,
        table: str,
        id_value: str,
        id_column: str = "id",
        select: str = "*",
    ) -> Optional[dict[str, Any]]:
        rows = await self.query(
            table, select=select, filters={id_column: f"eq.{id_value}"}, limit=1
        )
        return rows[0] if rows else None

    async def count(self, table: str, filters: Optional[dict[str, str]] = None) -> int:
        """Row count visible to the current tenant."""
        tenant = require()
        params = self._build_params("id", filters, None, 1, None)
        headers = self._headers(prefer="count=exact")
        # GET (not HEAD) so the gateway's record route always answers, and the
        # Content-Range header still carries the exact total under RLS.
        resp = await self._client.api_request(
            "GET",
            self._records_path(table),
            params=params,
            headers=headers,
            base="api",
            use_auth=False,
        )
        if resp.is_error:
            raise RlsViolation(f"count {table} failed ({resp.status_code}): {resp.text}")
        rng = resp.headers.get("content-range") or resp.headers.get("Content-Range") or ""
        total = rng.split("/")[-1].strip() if "/" in rng else ""
        try:
            return int(total)
        except (TypeError, ValueError):
            logger.debug("count fallback for %s (tenant=%s)", table, tenant.user_id)
            rows = await self.query(table, filters=filters, limit=1000)
            return len(rows)

    # ── writes ───────────────────────────────────────────────────

    async def create(
        self,
        table: str,
        data: dict[str, Any] | list[dict[str, Any]],
        *,
        prefer: str = "return=representation",
        inject_user_id: bool = True,
    ) -> list[dict[str, Any]]:
        """Insert rows, stamping ``user_id`` so RLS ``WITH CHECK`` passes."""
        tenant = require()
        rows = data if isinstance(data, list) else [data]
        payload = []
        for row in rows:
            item = dict(row)
            if inject_user_id and "user_id" not in item:
                item["user_id"] = tenant.user_id
            payload.append(item)

        result = await self._request(
            "POST", table, json_body=payload if len(payload) > 1 else payload[0], prefer=prefer
        )
        if result is None:
            return payload
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return [result]
        return payload

    async def update(
        self,
        table: str,
        filters: dict[str, str],
        data: dict[str, Any],
        *,
        prefer: str = "return=representation",
    ) -> list[dict[str, Any]]:
        if not filters:
            raise ValueError("refusing unfiltered update (would touch other tenants' rows)")
        result = await self._request(
            "PATCH", table, params=dict(filters), json_body=data, prefer=prefer
        )
        if result is None:
            return []
        return result if isinstance(result, list) else [result]

    async def update_by_id(
        self,
        table: str,
        id_value: str,
        data: dict[str, Any],
        id_column: str = "id",
    ) -> Optional[dict[str, Any]]:
        rows = await self.update(table, {id_column: f"eq.{id_value}"}, data)
        return rows[0] if rows else None

    async def delete(self, table: str, filters: dict[str, str]) -> None:
        if not filters:
            raise ValueError("refusing unfiltered delete (would touch other tenants' rows)")
        await self._request("DELETE", table, params=dict(filters))

    async def delete_by_id(self, table: str, id_value: str, id_column: str = "id") -> None:
        await self.delete(table, {id_column: f"eq.{id_value}"})

    # ── rpc ──────────────────────────────────────────────────────

    async def rpc(self, fn: str, payload: Optional[dict[str, Any]] = None) -> Any:
        """Call a Postgres function as the current user (RLS applies)."""
        tenant = require()
        resp = await self._client.api_request(
            "POST",
            f"/api/database/rpc/{fn}",
            json_body=payload or {},
            headers={"Authorization": f"Bearer {tenant.token}"},
            base="api",
            use_auth=False,
        )
        if resp.is_error:
            raise RlsViolation(f"rpc {fn} failed ({resp.status_code}): {resp.text}")
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    # ── upsert ───────────────────────────────────────────────────

    async def upsert(
        self,
        table: str,
        data: dict[str, Any] | list[dict[str, Any]],
        *,
        on_conflict: str = "id",
        inject_user_id: bool = True,
    ) -> list[dict[str, Any]]:
        tenant = require()
        rows = data if isinstance(data, list) else [data]
        payload = []
        for row in rows:
            item = dict(row)
            if inject_user_id and "user_id" not in item:
                item["user_id"] = tenant.user_id
            payload.append(item)
        params = {"on_conflict": on_conflict}
        result = await self._request(
            "POST",
            table,
            params=params,
            json_body=payload,
            prefer="return=representation,resolution=merge-duplicates",
        )
        if result is None:
            return payload
        return result if isinstance(result, list) else [result]

    async def fetch_owned(
        self,
        table: str,
        id_value: str,
        id_column: str = "id",
    ) -> dict[str, Any]:
        """Fetch a single row or raise — used where absence means 'not yours'."""
        row = await self.get_by_id(table, id_value, id_column=id_column)
        if row is None:
            raise RlsViolation(f"{table}.{id_column}={id_value} not visible to this tenant")
        return row

    async def exists(self, table: str, filters: dict[str, str]) -> bool:
        rows = await self.query(table, select="id", filters=filters, limit=1)
        return bool(rows)


def tenant_db(client: Any) -> TenantDB:
    return TenantDB(client)
