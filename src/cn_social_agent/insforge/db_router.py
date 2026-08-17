from __future__ import annotations

import asyncio
from typing import Any, Optional

from . import InsForge
from .db import InsForgeDB


_insforge_instance: Optional[InsForge] = None


def _get_insforge() -> Optional[InsForge]:
    """Get the global InsForge instance (lazy init)."""
    global _insforge_instance
    if _insforge_instance is not None:
        return _insforge_instance
    try:
        from cn_social_agent.insforge import InsForge
        insforge = InsForge()
        _insforge_instance = insforge
        return _insforge_instance
    except Exception:
        return None


def _sync_db_call(coro) -> Any:
    """Execute an async DB coroutine from a sync context."""
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            import concurrent.futures
            fut = asyncio.run_coroutine_threadsafe(coro, loop)
            return fut.result(timeout=30)
    except RuntimeError:
        pass
    return asyncio.run(coro)


def get_db() -> Optional[InsForgeDB]:
    """Get the InsForgeDB client if InsForge is enabled and available."""
    import os
    if os.getenv("INSFORGE_ENABLED", "true").lower() != "true":
        return None
    insforge = _get_insforge()
    if insforge is not None and insforge.enabled:
        return insforge.db
    return None


def db_enabled() -> bool:
    """Check if InsForge DB routing is enabled."""
    import os
    if os.getenv("INSFORGE_ENABLED", "true").lower() != "true":
        return False
    return _get_insforge() is not None


# Async helpers for inbox module (which uses async/await)
_async_db_client: Optional[InsForgeDB] = None


async def _aget_insforge() -> Optional[InsForge]:
    """Async version — also initializes admin_login."""
    global _insforge_instance
    if _insforge_instance is not None:
        return _insforge_instance
    try:
        from cn_social_agent.insforge import InsForge
        insforge = InsForge()
        try:
            await insforge.initialize()
        except Exception:
            pass
        _insforge_instance = insforge
        return _insforge_instance
    except Exception:
        return None


async def async_get_db() -> Optional[InsForgeDB]:
    """Get InsForgeDB client from async context (with admin_login)."""
    import os
    if os.getenv("INSFORGE_ENABLED", "true").lower() != "true":
        return None
    insforge = await _aget_insforge()
    if insforge is not None and insforge.enabled:
        return insforge.db
    return None


__all__ = [
    "get_db",
    "async_get_db",
    "db_enabled",
    "_sync_db_call",
]
