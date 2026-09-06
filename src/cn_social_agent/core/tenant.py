"""Tenant context for per-user isolation.

Every request that touches tenant data carries a :class:`TenantContext`.
The context holds the *end-user* InsForge JWT — never the admin key — so that
Postgres RLS policies (``user_id = auth.uid()``) do the isolation work in the
database itself instead of relying on application-level filtering.

Rules enforced by this module:

1. A tenant context is **required** for any tenant-scoped data access.
2. The admin credential never enters a tenant context.
3. :func:`system_context` is the only escape hatch, and it is reserved for
   server-side maintenance (schema provisioning, migration, ops repair). It
   must never be used to answer a user request.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import Any, Optional

# Locale used when the user has not expressed a preference.
DEFAULT_LOCALE = "zh-CN"
SUPPORTED_LOCALES = ("zh-CN", "en-US")

_current_tenant: contextvars.ContextVar[Optional["TenantContext"]] = (
    contextvars.ContextVar("cn_social_agent_current_tenant", default=None)
)

# Guard flag: set to True only inside explicit system/maintenance blocks.
_in_system_mode: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "cn_social_agent_system_mode", default=False
)


class TenantError(RuntimeError):
    """Raised when tenant scope is missing or violated."""


class IsolationViolation(RuntimeError):
    """Raised when code attempts to bypass tenant isolation improperly."""


@dataclass(frozen=True)
class TenantContext:
    """Identity + preferences of the acting end user."""

    user_id: str
    email: str = ""
    token: str = ""
    locale: str = DEFAULT_LOCALE

    # Free-form per-request metadata (trace id, ip, user agent ...).
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        return bool(self.user_id) and bool(self.token)

    def with_locale(self, locale: str) -> "TenantContext":
        return TenantContext(
            user_id=self.user_id,
            email=self.email,
            token=self.token,
            locale=normalize_locale(locale),
            meta=dict(self.meta),
        )

    def as_claims(self) -> dict[str, Any]:
        """Minimal identity view, safe to log."""
        return {"user_id": self.user_id, "email": self.email, "locale": self.locale}


def normalize_locale(raw: Optional[str]) -> str:
    """Map any user-supplied locale string onto a supported locale."""
    if not raw:
        return DEFAULT_LOCALE
    value = raw.strip().replace("_", "-")
    lowered = value.lower()
    for supported in SUPPORTED_LOCALES:
        if lowered == supported.lower():
            return supported
    # Accept bare language codes: zh, en, zh-Hans, en-GB ...
    base = lowered.split("-")[0]
    for supported in SUPPORTED_LOCALES:
        if supported.lower().split("-")[0] == base:
            return supported
    return DEFAULT_LOCALE


def bind(context: TenantContext) -> contextvars.Token:
    """Bind a tenant to the current execution context (async-safe)."""
    return _current_tenant.set(context)


def unbind(token: contextvars.Token) -> None:
    _current_tenant.reset(token)


def clear() -> None:
    """Drop the bound tenant without needing the original token.

    ``ContextVar.reset`` refuses tokens created in another execution context,
    which happens whenever a tenant is bound inside an asyncio task and torn
    down from a different one (tests, request lifecycles). Clearing is the
    safe teardown in those cases — it always leaves no tenant bound, which is
    the fail-closed outcome we want.
    """
    _current_tenant.set(None)


def current() -> Optional[TenantContext]:
    return _current_tenant.get()


def require() -> TenantContext:
    """Return the active tenant or fail loudly.

    Failing loudly is deliberate: silent fallback to a shared/system scope is
    exactly how cross-tenant leaks are introduced.
    """
    ctx = _current_tenant.get()
    if ctx is None or not ctx.user_id:
        raise TenantError("no tenant context bound to this operation")
    return ctx


def require_token() -> str:
    return require().token


def require_user_id() -> str:
    return require().user_id


@dataclass(frozen=True)
class SystemContext(TenantContext):
    """Explicit maintenance scope.

    Carries no user JWT and is therefore **not** accepted by tenant-scoped
    data access. It exists so that provisioning code can be statically
    distinguished from request handling code.
    """

    reason: str = ""

    @property
    def is_authenticated(self) -> bool:
        return False


def system_context(reason: str = "") -> SystemContext:
    return SystemContext(user_id="", email="", token="", locale=DEFAULT_LOCALE, reason=reason)


def bind_system(reason: str) -> contextvars.Token:
    token = _current_tenant.set(system_context(reason))
    _in_system_mode.set(True)
    return token


def is_system_mode() -> bool:
    return _in_system_mode.get()


def reset_system_mode() -> None:
    _in_system_mode.set(False)
