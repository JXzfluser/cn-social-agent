"""Nexus core: tenant isolation primitives built on InsForge.

Modules
-------
``tenant``   tenant context and locale (the identity carrier)
``db``       RLS-enforcing data access (what request code must use)
``admin``    schema / policy provisioning (maintenance only, bypasses RLS)
``storage``  user-namespaced private objects
``ai``       per-user model gateway calls
``i18n``     zh-CN / en-US runtime
``events``   execution trace streaming

The contract between them is simple: request handling code binds a tenant and
uses the tenant-scoped clients; provisioning code uses the admin gateway and
never runs inside a tenant request.
"""

from __future__ import annotations

from .tenant import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    IsolationViolation,
    SystemContext,
    TenantContext,
    TenantError,
    bind,
    bind_system,
    clear,
    current,
    is_system_mode,
    normalize_locale,
    require,
    require_token,
    require_user_id,
    reset_system_mode,
    system_context,
    unbind,
)
from .db import RlsViolation, TenantDB, tenant_db
from .admin import AdminError, AdminGateway, Column, Table, admin_gateway
from .storage import DEFAULT_BUCKET, StorageError, TenantStorage, tenant_storage
from .ai import AiError, TenantAI, tenant_ai
from .i18n import available_locales, dictionary, output_language_hint, t, translate
from .events import Event, EventBus, bus, emit, task_stream

__all__ = [
    "DEFAULT_LOCALE",
    "SUPPORTED_LOCALES",
    "IsolationViolation",
    "SystemContext",
    "TenantContext",
    "TenantError",
    "bind",
    "bind_system",
    "clear",
    "current",
    "is_system_mode",
    "normalize_locale",
    "require",
    "require_token",
    "require_user_id",
    "reset_system_mode",
    "system_context",
    "unbind",
    "RlsViolation",
    "TenantDB",
    "tenant_db",
    "AdminError",
    "AdminGateway",
    "Column",
    "Table",
    "admin_gateway",
    "DEFAULT_BUCKET",
    "StorageError",
    "TenantStorage",
    "tenant_storage",
    "AiError",
    "TenantAI",
    "tenant_ai",
    "available_locales",
    "dictionary",
    "output_language_hint",
    "t",
    "translate",
    "Event",
    "EventBus",
    "bus",
    "emit",
    "task_stream",
]
