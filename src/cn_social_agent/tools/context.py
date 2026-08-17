"""Per-request tool context (user + store handles) via contextvars."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any, Optional

_CTX: ContextVar[dict[str, Any]] = ContextVar("wb_tool_ctx", default={})


def set_tool_context(**kwargs: Any) -> Token:
    cur = dict(_CTX.get() or {})
    cur.update({k: v for k, v in kwargs.items() if v is not None})
    return _CTX.set(cur)


def reset_tool_context(token: Token) -> None:
    _CTX.reset(token)


def get_tool_context() -> dict[str, Any]:
    return dict(_CTX.get() or {})


def tool_user_id() -> str:
    return str(get_tool_context().get("user_id") or "").strip()


def tool_email() -> str:
    return str(get_tool_context().get("email") or "").strip()
