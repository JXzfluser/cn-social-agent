"""In-memory stand-ins for InsForge used by the Nexus test suite.

The fake client speaks just enough of the PostgREST-over-InsForge protocol
(``/api/database/records/*`` with ``col=eq.value`` filters, ``order``,
``limit``/``offset``, ``Prefer: return=representation``) to exercise the real
:class:`~cn_social_agent.core.db.TenantDB` code path.

Crucially it **enforces the RLS contract itself**: when a request carries a
user JWT, rows are filtered by ``user_id == <sub>`` and inserts are rejected if
``user_id`` does not match. That means isolation tests fail here for the same
reason they would fail against real Postgres, instead of passing vacuously.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import pytest

from cn_social_agent.core import bind, clear
from cn_social_agent.core.tenant import TenantContext
from cn_social_agent.experts import ExpertRegistry
from cn_social_agent.tasks import ReviewEngine, TaskEngine

# Minimal claim extraction mirroring InsForge: JWT payload {sub, email, role}.
_ANON_TOKENS = {"", "anon", "anon_key"}


class RlsDenied(Exception):
    """Raised when the fake engine rejects a write under RLS."""


@dataclass
class FakeResponse:
    status_code: int
    _body: Any = None
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def content(self) -> bytes:
        if self._body is None:
            return b""
        return json.dumps(self._body, ensure_ascii=False, default=str).encode()

    @property
    def text(self) -> str:
        return self.content.decode()

    @property
    def is_error(self) -> bool:
        return self.status_code >= 400

    def json(self) -> Any:
        if self._body is None:
            return None
        return self._body


class FakeInsForge:
    """PostgREST-shaped in-memory database with RLS enforcement."""

    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.rls_tables: set[str] = set()
        self.audit: list[tuple[str, str, str]] = []  # (user, method, table)
        self._seq = 0

    def _stamp(self) -> str:
        """Monotonic timestamps so ``order=created_at.desc`` is deterministic."""
        self._seq += 1
        return f"2026-01-01T00:00:00.{self._seq:09d}+00:00"

    # ── schema ───────────────────────────────────────────────────

    def create_table(self, name: str, rls: bool = True) -> None:
        self.tables.setdefault(name, [])
        if rls:
            self.rls_tables.add(name)

    def insert_raw(self, table: str, rows: list[dict[str, Any]]) -> None:
        """Bypass RLS — only for seeding fixtures."""
        self.tables.setdefault(table, []).extend(rows)

    # ── protocol ─────────────────────────────────────────────────

    @staticmethod
    def _identity(token: Optional[str]) -> tuple[Optional[str], bool]:
        """Return (user_id, is_admin) for a bearer token."""
        if not token or token in _ANON_TOKENS:
            return None, False
        if token.startswith("admin:"):
            return None, True
        if token.startswith("user:"):
            return token.split(":", 1)[1], False
        return token, False

    @staticmethod
    def _parse_filters(params: dict[str, Any]) -> dict[str, tuple[str, str]]:
        filters: dict[str, tuple[str, str]] = {}
        for key, value in (params or {}).items():
            if key in ("select", "order", "limit", "offset", "on_conflict"):
                continue
            if isinstance(value, str) and "." in value:
                op, _, operand = value.partition(".")
                filters[key] = (op, operand)
            else:
                filters[key] = ("eq", str(value))
        return filters

    def _visible(self, table: str, user_id: Optional[str], is_admin: bool) -> list[dict]:
        rows = self.tables.get(table, [])
        if is_admin or table not in self.rls_tables:
            return list(rows)
        if user_id is None:
            return []
        return [r for r in rows if str(r.get("user_id")) == str(user_id)]

    def _apply(
        self, rows: list[dict], params: dict[str, Any]
    ) -> list[dict]:
        filtered = rows
        for column, (op, operand) in self._parse_filters(params).items():
            if op == "eq":
                filtered = [r for r in filtered if str(r.get(column)) == operand]
            elif op == "neq":
                filtered = [r for r in filtered if str(r.get(column)) != operand]
            elif op == "in":
                values = operand.strip("()").split(",")
                filtered = [r for r in filtered if str(r.get(column)) in values]
            elif op == "is":
                filtered = [
                    r for r in filtered
                    if (operand == "null" and r.get(column) is None)
                    or (operand == "not.null" and r.get(column) is not None)
                ]
        order = params.get("order")
        if order:
            column, _, direction = str(order).partition(".")
            filtered = sorted(
                filtered,
                key=lambda r: str(r.get(column) or ""),
                reverse=direction == "desc",
            )
        offset = int(params.get("offset") or 0)
        limit = params.get("limit")
        if limit is not None:
            filtered = filtered[offset : offset + int(limit)]
        elif offset:
            filtered = filtered[offset:]
        return filtered

    # ── client interface (duck-types InsForgeClient) ─────────────

    async def api_request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        base: str = "api",
        use_auth: bool = True,
    ) -> FakeResponse:
        headers = headers or {}
        params = params or {}
        token = _bearer(headers)
        user_id, is_admin = self._identity(token)

        match = re.match(r"^/api/database/records/([A-Za-z0-9_]+)$", path)
        if not match:
            return FakeResponse(404, {"error": f"no route {path}"})
        table = match.group(1)
        if table not in self.tables:
            return FakeResponse(404, {"error": f"table {table} not found"})
        self.audit.append((user_id or "anon", method.upper(), table))

        method = method.upper()
        if method == "GET":
            rows = self._apply(self._visible(table, user_id, is_admin), params)
            out_headers = {}
            prefer = headers.get("Prefer") or headers.get("prefer") or ""
            if "count=exact" in prefer:
                total = len(self._apply(self._visible(table, user_id, is_admin),
                                        {k: v for k, v in params.items() if k != "limit"}))
                out_headers["content-range"] = f"0-{max(0, len(rows) - 1)}/{total}"
            return FakeResponse(200, rows, out_headers)

        if method == "POST":
            return self._insert(table, json_body, user_id, is_admin, headers, params)

        if method == "PATCH":
            targets = self._apply(self._visible(table, user_id, is_admin), params)
            if not params:
                return FakeResponse(400, {"error": "unfiltered update"})
            for row in targets:
                for key, value in (json_body or {}).items():
                    if key == "user_id" and table in self.rls_tables and not is_admin:
                        if str(value) != str(row.get("user_id")):
                            return FakeResponse(403, {"error": "row violates RLS"})
                    row[key] = value
            return FakeResponse(200, targets)

        if method == "DELETE":
            if not params:
                return FakeResponse(400, {"error": "unfiltered delete"})
            targets = self._apply(self._visible(table, user_id, is_admin), params)
            for row in targets:
                self.tables[table].remove(row)
            return FakeResponse(204)

        return FakeResponse(405, {"error": f"method {method}"})

    def _insert(
        self,
        table: str,
        body: Any,
        user_id: Optional[str],
        is_admin: bool,
        headers: dict,
        params: dict,
    ) -> FakeResponse:
        rows = body if isinstance(body, list) else [body]
        stored = self.tables.setdefault(table, [])
        created = []
        for row in rows:
            item = dict(row or {})
            item.setdefault("id", f"{table}-{len(stored) + len(created) + 1}")
            item.setdefault("created_at", self._stamp())
            # RLS WITH CHECK: an authenticated caller may only write its own rows.
            if table in self.rls_tables and not is_admin:
                if user_id is None:
                    return FakeResponse(403, {"error": "anonymous write denied by RLS"})
                if str(item.get("user_id")) != str(user_id):
                    return FakeResponse(
                        403, {"error": "new row violates row-level security policy"}
                    )
            stored.append(item)
            created.append(item)
        prefer = headers.get("Prefer") or ""
        if "return=representation" in prefer:
            return FakeResponse(201, created if isinstance(body, list) else created[0])
        return FakeResponse(201)

    async def api_post(self, path: str, json_body: Any = None, **kw) -> Any:
        resp = await self.api_request("POST", path, json_body=json_body, **kw)
        if resp.is_error:
            raise RuntimeError(f"POST {path} failed ({resp.status_code}): {resp.text}")
        if resp.status_code == 204:
            return None
        return resp.json()

    async def api_get(self, path: str, **kw) -> Any:
        resp = await self.api_request("GET", path, **kw)
        if resp.is_error:
            raise RuntimeError(f"GET {path} failed ({resp.status_code}): {resp.text}")
        return resp.json()

    async def api_patch(self, path: str, json_body: Any = None, **kw) -> Any:
        resp = await self.api_request("PATCH", path, json_body=json_body, **kw)
        if resp.is_error:
            raise RuntimeError(f"PATCH {path} failed ({resp.status_code}): {resp.text}")
        return resp.json()

    async def api_delete(self, path: str, **kw) -> None:
        resp = await self.api_request("DELETE", path, **kw)
        if resp.is_error:
            raise RuntimeError(f"DELETE {path} failed ({resp.status_code}): {resp.text}")

    # convenience so tests can read the raw store
    def rows(self, table: str) -> list[dict]:
        return self.tables.get(table, [])

    @property
    def config(self) -> Any:
        class _Cfg:
            api_url = "http://fake"
            llm = type("L", (), {"default_model": "test-model"})()

        return _Cfg()


def _bearer(headers: dict) -> Optional[str]:
    raw = headers.get("Authorization") or headers.get("authorization") or ""
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return None


# ── fixtures ─────────────────────────────────────────────────────


NEXUS_TABLES = ("wb_nexus_tasks", "wb_nexus_steps", "wb_nexus_artifacts", "wb_nexus_reviews")


@pytest.fixture
def fake():
    db = FakeInsForge()
    for table in NEXUS_TABLES:
        db.create_table(table)
    return db


@pytest.fixture
def registry():
    return ExpertRegistry().scan()


@pytest.fixture
def as_user():
    """Bind a tenant context for the duration of a test."""

    def _bind(user_id: str, email: str = "", locale: str = "zh-CN"):
        ctx = TenantContext(
            user_id=user_id,
            email=email or f"{user_id}@test.local",
            token=f"user:{user_id}",
            locale=locale,
        )
        bind(ctx)
        return ctx

    yield _bind
    clear()


@pytest.fixture
def engine_factory(fake, registry):
    def _make():
        return TaskEngine(fake, registry, db=_db(fake))
    return _make


def _db(fake):
    from cn_social_agent.core.db import TenantDB

    return TenantDB(fake)


@pytest.fixture
def reviewer():
    return ReviewEngine()
