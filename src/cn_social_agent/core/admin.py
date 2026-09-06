"""InsForge administrative gateway — schema provisioning and RLS policy management.

This is the **maintenance** counterpart to :mod:`cn_social_agent.core.db`.
It talks to InsForge with the project admin credential (``ik_`` API key or
project_admin JWT) and is therefore able to:

* create / alter tables,
* execute raw SQL,
* create and inspect row-level security policies.

Hard boundary
-------------
``AdminGateway`` must **never** be used to serve a tenant request. It bypasses
RLS by design. It is wired only into provisioning scripts and ops tooling, and
it refuses to run while a tenant context is bound unless the caller explicitly
declares system mode via :func:`cn_social_agent.core.tenant.bind_system`.

This is the piece that turns "isolation by remembering to filter" into
"isolation enforced by the database".
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .tenant import is_system_mode, current

logger = logging.getLogger(__name__)

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Column types accepted by InsForge's create-table schema.
COLUMN_TYPES = frozenset(
    {"string", "text", "date", "datetime", "integer", "float", "boolean", "uuid", "json"}
)


class AdminError(RuntimeError):
    pass


@dataclass
class Column:
    name: str
    type: str = "string"
    nullable: bool = True
    unique: bool = False
    default: Optional[str] = None

    def __post_init__(self) -> None:
        if not _IDENT_RE.match(self.name):
            raise AdminError(f"invalid column name: {self.name!r}")
        if self.type not in COLUMN_TYPES:
            raise AdminError(f"unsupported column type: {self.type!r}")

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "columnName": self.name,
            "type": self.type,
            "isNullable": self.nullable,
            "isUnique": self.unique,
        }
        if self.default is not None:
            payload["defaultValue"] = self.default
        return payload


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    rls_enabled: bool = True
    foreign_keys: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not _IDENT_RE.match(self.name):
            raise AdminError(f"invalid table name: {self.name!r}")

    def to_payload(self) -> dict[str, Any]:
        return {
            "tableName": self.name,
            "rlsEnabled": self.rls_enabled,
            "columns": [c.to_payload() for c in self.columns],
            "foreignKeys": self.foreign_keys,
        }


class AdminGateway:
    """Admin-plane client for InsForge database management."""

    def __init__(self, client: Any) -> None:
        self._client = client

    # ── guardrails ───────────────────────────────────────────────

    @staticmethod
    def _assert_maintenance_scope() -> None:
        ctx = current()
        # Allowed when: no tenant bound (startup/provisioning), or the caller
        # explicitly opted into system mode. Never allowed inside a user request.
        if ctx is not None and ctx.user_id and not is_system_mode():
            raise AdminError(
                "AdminGateway used inside a tenant request — this would bypass RLS. "
                "Use core.db.TenantDB for tenant data."
            )

    @staticmethod
    def _quote(ident: str) -> str:
        if not _IDENT_RE.match(ident):
            raise AdminError(f"unsafe identifier: {ident!r}")
        return f'"{ident}"'

    # ── raw SQL ──────────────────────────────────────────────────

    async def exec_sql(self, sql: str, unrestricted: bool = True) -> Any:
        """Execute raw SQL as project admin.

        Defaults to the unrestricted (root) endpoint because provisioning needs
        DDL (``GRANT`` / ``CREATE POLICY`` / ``ALTER TABLE ... ENABLE ROW LEVEL
        SECURITY``) that the project_admin role cannot perform through the
        restricted endpoint. This is maintenance-only, guarded by
        :meth:`_assert_maintenance_scope`, so unrestricted is the correct call.
        """
        self._assert_maintenance_scope()
        await self._client._ensure_admin_token()
        path = "/api/database/advance/rawsql/unrestricted" if unrestricted else "/api/database/advance/rawsql"
        return await self._client.api_post(path, json_body={"query": sql}, use_auth=True)

    # ── tables ───────────────────────────────────────────────────

    async def list_tables(self) -> list[str]:
        self._assert_maintenance_scope()
        await self._client._ensure_admin_token()
        data = await self._client.api_get("/api/database/tables", use_auth=True)
        if isinstance(data, list):
            names: list[str] = []
            for item in data:
                if isinstance(item, dict):
                    name = item.get("tableName") or item.get("table_name") or item.get("name")
                    if name:
                        names.append(str(name))
            return names
        tables = data.get("tables") if isinstance(data, dict) else []
        return [str(t.get("tableName") or t) for t in (tables or [])]

    async def create_table(self, table: Table) -> bool:
        """Create a table. Returns True if created, False if it already existed."""
        self._assert_maintenance_scope()
        await self._client._ensure_admin_token()
        try:
            existing = await self.list_tables()
        except Exception:  # noqa: BLE001
            existing = []
        if table.name in existing:
            logger.info("table %s already exists, skipping create", table.name)
            return False
        try:
            await self._client.api_post(
                "/api/database/tables", json_body=table.to_payload(), use_auth=True
            )
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            # Idempotent re-run: the table may already exist from a prior pass.
            if "already exists" in msg or "DATABASE_DUPLICATE" in msg:
                logger.info("table %s already exists, skipping create", table.name)
                return False
            # Race with a concurrent provisioner is benign; verify instead.
            logger.warning("create table %s reported %s; verifying", table.name, exc)
            try:
                existing2 = await self.list_tables()
            except Exception:  # noqa: BLE001
                existing2 = []
            if table.name in existing2:
                return False
            raise AdminError(f"create table {table.name} failed: {exc}") from exc
        return True

    async def add_column_if_missing(
        self, table: str, column: Column, default_sql: Optional[str] = None
    ) -> bool:
        """Idempotent ALTER TABLE ADD COLUMN via raw SQL."""
        self._assert_maintenance_scope()
        qualified = f"public.{self._quote(table)}"
        ddl = f"ALTER TABLE {qualified} ADD COLUMN IF NOT EXISTS {self._quote(column.name)}"
        ddl += f" {self._pg_type(column.type)}"
        if not column.nullable:
            # Backfill existing rows before enforcing NOT NULL.
            if default_sql:
                await self.exec_sql(
                    f"UPDATE {qualified} SET {self._quote(column.name)} = {default_sql} "
                    f"WHERE {self._quote(column.name)} IS NULL"
                )
            ddl += f" DEFAULT {default_sql}" if default_sql else ""
        elif column.default is not None:
            ddl += f" DEFAULT {self._pg_type_default(column.default)}"
        await self.exec_sql(ddl + ";")
        return True

    @staticmethod
    def _pg_type(kind: str) -> str:
        return {
            "string": "text",
            "text": "text",
            "date": "date",
            "datetime": "timestamptz",
            "integer": "integer",
            "float": "double precision",
            "boolean": "boolean",
            "uuid": "uuid",
            "json": "jsonb",
        }[kind]

    @staticmethod
    def _pg_type_default(raw: str) -> str:
        if raw.lower() in ("now()", "gen_random_uuid()", "true", "false"):
            return raw
        if raw.startswith("'") or raw.replace(".", "").replace("-", "").isdigit():
            return raw
        return f"'{raw}'"

    # ── RLS ──────────────────────────────────────────────────────

    async def grant_table(self, table: str, roles: tuple[str, ...] = ("authenticated",)) -> None:
        """Grant DML so PostgREST callers (not the table owner) can use the table.

        RLS still governs *which* rows; grants only govern *whether* the role
        may touch the table at all.
        """
        self._assert_maintenance_scope()
        qualified = f"public.{self._quote(table)}"
        for role in roles:
            if role not in ("authenticated", "anon"):
                raise AdminError(f"refusing to grant to unexpected role: {role}")
            await self.exec_sql(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {qualified} TO {role};"
            )

    async def ensure_rls(
        self,
        table: str,
        user_column: str = "user_id",
        *,
        owner_read: bool = True,
        public_read: bool = False,
        grant_roles: tuple[str, ...] = ("authenticated",),
    ) -> list[str]:
        """Enable RLS and (re)create the four per-user policies.

        The policy set is the whole point of the isolation model:

        * SELECT / UPDATE / DELETE  →  ``USING (user_id = auth.uid())``
        * INSERT                    →  ``WITH CHECK (user_id = auth.uid())``

        ``public_read`` additionally grants SELECT to ``anon`` for genuinely
        public content (e.g. the expert catalogue), which is opt-in and never
        the default for tenant data.
        """
        self._assert_maintenance_scope()
        qualified = f"public.{self._quote(table)}"
        col = self._quote(user_column)
        applied: list[str] = []

        await self.exec_sql(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY;")
        await self.exec_sql(f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY;")
        applied.append("rls_enabled")

        await self.grant_table(table, grant_roles)

        for cmd in ("select", "insert", "update", "delete"):
            policy = f"{table}_{cmd}_own"
            await self.exec_sql(f"DROP POLICY IF EXISTS {self._quote(policy)} ON {qualified};")

        await self.exec_sql(
            f"CREATE POLICY {self._quote(table + '_select_own')} ON {qualified} "
            f"FOR SELECT TO authenticated USING ({col} = auth.uid());"
        )
        await self.exec_sql(
            f"CREATE POLICY {self._quote(table + '_insert_own')} ON {qualified} "
            f"FOR INSERT TO authenticated WITH CHECK ({col} = auth.uid());"
        )
        await self.exec_sql(
            f"CREATE POLICY {self._quote(table + '_update_own')} ON {qualified} "
            f"FOR UPDATE TO authenticated USING ({col} = auth.uid()) "
            f"WITH CHECK ({col} = auth.uid());"
        )
        await self.exec_sql(
            f"CREATE POLICY {self._quote(table + '_delete_own')} ON {qualified} "
            f"FOR DELETE TO authenticated USING ({col} = auth.uid());"
        )
        applied.extend([f"{table}_{c}_own" for c in ("select", "insert", "update", "delete")])

        if public_read:
            anon_policy = f"{table}_select_public"
            await self.exec_sql(
                f"DROP POLICY IF EXISTS {self._quote(anon_policy)} ON {qualified};"
            )
            await self.exec_sql(
                f"CREATE POLICY {self._quote(anon_policy)} ON {qualified} "
                f"FOR SELECT TO anon USING (true);"
            )
            applied.append(anon_policy)
        elif owner_read:
            # Belt and braces: ensure no anonymous read policy lingers.
            await self.exec_sql(
                f"DROP POLICY IF EXISTS {self._quote(table + '_select_public')} ON {qualified};"
            )

        return applied

    async def list_policies(self, table: Optional[str] = None) -> list[dict[str, Any]]:
        self._assert_maintenance_scope()
        await self._client._ensure_admin_token()
        params = {"tableName": table} if table else None
        data = await self._client.api_get("/api/database/policies", params=params, use_auth=True)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("policies", "data", "items"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        return []

    async def has_rls(self, table: str) -> bool:
        if not _IDENT_RE.match(table):
            raise AdminError(f"unsafe identifier: {table!r}")
        rows = await self.exec_sql(
            "SELECT c.relrowsecurity AS rls FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            f"WHERE n.nspname = 'public' AND c.relname = '{table}';",
        )
        try:
            data = rows if isinstance(rows, list) else (rows or {}).get("data") or (rows or {}).get("rows")
            if data:
                return bool(data[0].get("rls", False))
        except Exception:  # noqa: BLE001
            pass
        return False


def admin_gateway(client: Any) -> AdminGateway:
    return AdminGateway(client)
