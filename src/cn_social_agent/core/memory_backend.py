"""In-memory InsForge-compatible backend.

This is a **drop-in** for :class:`cn_social_agent.insforge.client.InsForgeClient`
for the subset of the API the Nexus workbench uses:

* ``/api/database/records/*``  (the PostgREST surface that :class:`TenantDB`
  talks to)
* ``/api/ai/chat/completion``   (the model gateway that :class:`TenantAI` calls)

Why it exists
-------------
The production path is a real InsForge (Postgres + PostgREST + RLS). But the
workbench must also *boot and be exercisable* when InsForge is unreachable —
local dev, CI smoke tests, a quick demo. Rather than special-casing every
route, this module emulates the gateway closely enough that the very same
:class:`TenantDB` / :class:`TenantAI` / :class:`TaskEngine` code runs on top of
it unchanged.

Isolation is **not** faked away. Just as the real gateway re-signs the user's
token and Postgres enforces ``user_id = auth.uid()`` via RLS, this backend
resolves the bearer token to a user id and refuses any row that is not owned by
that user. A request with no resolvable user is answered ``401`` — exactly the
fail-closed behaviour the database gives us. So the "per-user isolation"
contract holds in memory too.

The AI endpoint intentionally returns a gateway error, so runners take their
deterministic offline path. That keeps the acceptance loop honest: a draft only
becomes "approved" because the rubric *and* the human gate say so, never
because a model happened to be online.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Callable, Optional

# Operators TenantDB is willing to emit (mirrors core/db.py _SAFE_OPS).
_SAFE_OPS = {
    "eq", "neq", "gt", "gte", "lt", "lte", "like", "ilike",
    "is", "in", "cs", "cd", "ov", "sl", "sr", "nxl", "nxr", "adj",
}


class _MemoryLLMConfig:
    default_model = "mock/offline"


class _MemoryConfig:
    llm = _MemoryLLMConfig()
    enabled = False


class _FakeResponse:
    """Minimal httpx.Response shim used by the InsForge client surface."""

    def __init__(
        self,
        status_code: int,
        json_data: Any = None,
        text: str = "",
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.status_code = status_code
        self._json = json_data
        self.text = text or (json.dumps(json_data, ensure_ascii=False) if json_data is not None else "")
        self.headers: dict[str, str] = {k.lower(): str(v) for k, v in (headers or {}).items()}
        self.content = self.text.encode("utf-8")
        self.is_error = status_code >= 400

    def json(self) -> Any:
        if self._json is not None:
            return self._json
        if self.content:
            return json.loads(self.content)
        return None

    async def aiter_lines(self):  # pragma: no cover - not used in memory mode
        return
        yield  # type: ignore[misc,return-value]


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex}" if prefix else uuid.uuid4().hex


class MemoryInsForgeClient:
    """Process-local, RLS-enforcing emulator of the InsForge client.

    ``resolve_user`` maps a bearer token to a user id. In the workbench, memory
    auth already issues tokens, so this just forwards to ``MemoryStore``.
    """

    def __init__(self, resolve_user: Callable[[str], Optional[str]]) -> None:
        self.config = _MemoryConfig()
        self._resolve_user = resolve_user
        self._tables: dict[str, list[dict[str, Any]]] = {}
        self._lock: Any = None  # set lazily to an asyncio.Lock

    # ── helpers ──────────────────────────────────────────────────

    def _get_lock(self):
        import asyncio

        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _user_id(self, headers: Optional[dict[str, str]]) -> Optional[str]:
        headers = headers or {}
        auth = headers.get("Authorization") or headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
            if token:
                return self._resolve_user(token)
        return None

    @staticmethod
    def _parse_filter(key: str, value: str) -> Optional[tuple[str, str, str]]:
        if key in ("select", "order", "limit", "offset"):
            return None
        m = re.match(r"^(\w+)\.(.+)$", str(value))
        if m and m.group(1) in _SAFE_OPS:
            return (key, m.group(1), m.group(2))
        return (key, "eq", str(value))

    @staticmethod
    def _match(row: dict[str, Any], column: str, op: str, value: str) -> bool:
        actual = row.get(column)
        if op == "eq":
            return str(actual) == str(value)
        if op == "neq":
            return str(actual) != str(value)
        if op == "is":
            return (actual is None) if value == "null" else (actual is not None)
        try:
            a, b = float(actual), float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False
        return {
            "gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b,
        }.get(op, False)

    def _owned(self, table: str, user_id: str) -> list[dict[str, Any]]:
        rows = self._tables.setdefault(table, [])
        return [r for r in rows if r.get("user_id") == user_id]

    # ── records emulator ─────────────────────────────────────────

    async def _records(
        self,
        method: str,
        table: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Any = None,
        headers: Optional[dict[str, str]] = None,
    ) -> _FakeResponse:
        import asyncio

        async with self._get_lock():
            user_id = self._user_id(headers)
            if not user_id:
                return _FakeResponse(401, text="unauthorized")
            params = params or {}

            if method == "POST":
                return self._records_insert(table, user_id, json_body)
            if method == "GET":
                return self._records_select(table, user_id, params, headers)
            if method == "PATCH":
                return self._records_update(table, user_id, params, json_body)
            if method == "DELETE":
                return self._records_delete(table, user_id, params)
            return _FakeResponse(405, text="method not allowed")

    def _records_insert(self, table: str, user_id: str, json_body: Any) -> _FakeResponse:
        rows = self._tables.setdefault(table, [])
        items = json_body if isinstance(json_body, list) else [json_body]
        created: list[dict[str, Any]] = []
        on_conflict = None
        for item in items:
            if not isinstance(item, dict):
                continue
            data = dict(item)
            data["user_id"] = user_id  # gateway guarantees ownership
            if "id" not in data or not data["id"]:
                data["id"] = _new_id()
            rows.append(data)
            created.append(data)
        if on_conflict is not None:
            pass  # (upsert handled in api_request via params; see below)
        if isinstance(json_body, list):
            return _FakeResponse(201, json_data=created)
        return _FakeResponse(201, json_data=created[0] if created else None)

    def _records_select(
        self,
        table: str,
        user_id: str,
        params: dict[str, Any],
        headers: Optional[dict[str, str]],
    ) -> _FakeResponse:
        rows = self._owned(table, user_id)
        for key, value in params.items():
            f = self._parse_filter(key, value)
            if f is None:
                continue
            col, op, val = f
            rows = [r for r in rows if self._match(r, col, op, val)]

        order = params.get("order")
        if order:
            col, _, direction = str(order).partition(".")
            desc = direction.lower() == "desc"
            rows = sorted(
                rows,
                key=lambda r: (r.get(col) is None, str(r.get(col))),
                reverse=desc,
            )

        total = len(rows)
        offset = int(params.get("offset") or 0)
        limit = params.get("limit")
        if limit is not None:
            try:
                limit = int(limit)
            except (TypeError, ValueError):
                limit = None
        page = rows[offset : (offset + limit) if limit is not None else None]

        resp_headers: dict[str, str] = {}
        prefer = (headers or {}).get("Prefer") or (headers or {}).get("prefer") or ""
        if "count=exact" in prefer:
            end = offset + len(page) - 1 if page else offset
            resp_headers["Content-Range"] = f"{offset}-{end}/{total}"
        return _FakeResponse(200, json_data=page, headers=resp_headers)

    def _records_update(
        self, table: str, user_id: str, params: dict[str, Any], json_body: Any
    ) -> _FakeResponse:
        rows = self._owned(table, user_id)
        targets: list[dict[str, Any]] = []
        for r in rows:
            ok = True
            for key, value in params.items():
                f = self._parse_filter(key, value)
                if f is None:
                    continue
                if not self._match(r, *f):
                    ok = False
                    break
            if ok:
                targets.append(r)
        patch = {k: v for k, v in (json_body or {}).items() if k != "user_id"}
        for r in targets:
            r.update(patch)
        return _FakeResponse(200, json_data=targets)

    def _records_delete(self, table: str, user_id: str, params: dict[str, Any]) -> _FakeResponse:
        rows = self._tables.setdefault(table, [])
        keep: list[dict[str, Any]] = []
        removed = 0
        for r in rows:
            if r.get("user_id") != user_id:
                keep.append(r)
                continue
            ok = True
            for key, value in params.items():
                f = self._parse_filter(key, value)
                if f is None:
                    continue
                if not self._match(r, *f):
                    ok = False
                    break
            if ok:
                removed += 1
            else:
                keep.append(r)
        self._tables[table] = keep
        return _FakeResponse(204 if removed else 200, json_data=[])

    # ── InsForgeClient-compatible surface ────────────────────────

    async def api_request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        use_auth: bool = True,
        base: str = "api",
    ) -> _FakeResponse:
        if path.startswith("/api/database/records/"):
            table = path[len("/api/database/records/"):].strip("/")
            # Support upsert on_conflict param (PostgREST uses ?on_conflict=col)
            oc = (params or {}).get("on_conflict") if params else None
            resp = await self._records(method, table, params=params, json_body=json_body, headers=headers)
            if oc and method == "POST" and resp.status_code < 400:
                self._apply_upsert(table, oc, resp)
            return resp
        if path == "/api/ai/chat/completion":
            # No model in memory mode → emulate gateway outage so runners fall back.
            return _FakeResponse(
                502, text="AI gateway unavailable in memory mode",
                json_data={"error": "AI gateway unavailable in memory mode"},
            )
        if path.startswith("/api/database/") or path.startswith("/api/storage/"):
            # Provisioning / storage are not exercised in memory mode.
            return _FakeResponse(404, text="not implemented in memory backend")
        return _FakeResponse(404, text="unknown path in memory backend")

    def _apply_upsert(self, table: str, on_conflict: str, resp: _FakeResponse) -> None:
        """Merge duplicate inserts onto the same conflict column for one user."""
        incoming = resp.json() if isinstance(resp.json(), list) else (
            [resp.json()] if resp.json() else []
        )
        rows = self._tables.setdefault(table, [])
        for new in incoming:
            if not isinstance(new, dict):
                continue
            key = new.get(on_conflict)
            for idx, r in enumerate(rows):
                if r.get("user_id") == new.get("user_id") and r.get(on_conflict) == key:
                    rows[idx] = {**r, **new}
                    break

    async def api_get(self, path: str, **kw) -> Any:
        resp = await self.api_request("GET", path, **kw)
        if resp.is_error:
            raise RuntimeError(f"GET {path} failed: {resp.text}")
        return resp.json()

    async def api_post(self, path: str, json_body: Any = None, **kw) -> Any:
        resp = await self.api_request("POST", path, json_body=json_body, **kw)
        if resp.is_error:
            raise RuntimeError(f"POST {path} failed: {resp.text}")
        if resp.status_code == 204:
            return None
        return resp.json()

    async def api_put(self, path: str, json_body: Any = None, **kw) -> Any:
        resp = await self.api_request("PUT", path, json_body=json_body, **kw)
        if resp.is_error:
            raise RuntimeError(f"PUT {path} failed: {resp.text}")
        return resp.json()

    async def api_patch(self, path: str, json_body: Any = None, **kw) -> Any:
        resp = await self.api_request("PATCH", path, json_body=json_body, **kw)
        if resp.is_error:
            raise RuntimeError(f"PATCH {path} failed: {resp.text}")
        return resp.json()

    async def api_delete(self, path: str, **kw) -> None:
        resp = await self.api_request("DELETE", path, **kw)
        if resp.is_error:
            raise RuntimeError(f"DELETE {path} failed: {resp.text}")

    async def close(self) -> None:  # pragma: no cover - nothing to release
        return None


def memory_client(resolve_user: Callable[[str], Optional[str]]) -> MemoryInsForgeClient:
    return MemoryInsForgeClient(resolve_user)
