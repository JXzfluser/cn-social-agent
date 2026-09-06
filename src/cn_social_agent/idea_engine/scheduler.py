from __future__ import annotations

import asyncio
import logging

from cn_social_agent.idea_engine.engine import engine

logger = logging.getLogger(__name__)

_scheduler_task = None
_app = None


def set_app(app):
    global _app
    _app = app


async def sync_all_users():
    if not _app:
        return

    state = _app.get("state")
    if not state:
        return

    try:
        store = state.store
        if hasattr(store, "list_users"):
            users = await store.list_users()
        else:
            users = []
    except Exception:
        return

    for user in users:
        user_id = user.get("id") or user.get("user_id")
        if not user_id:
            continue

        try:
            materials = await engine.sync_materials(user_id)
            logger.info(f"Synced {len(materials)} materials for user {user_id}")
        except Exception as e:
            logger.error(f"Sync failed for user {user_id}: {e}")


async def _scheduler_loop(interval_hours: int = 6):
    while True:
        try:
            await sync_all_users()
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(interval_hours * 3600)


def start_scheduler(interval_hours: int = 6):
    global _scheduler_task
    if _scheduler_task is None:
        _scheduler_task = asyncio.create_task(_scheduler_loop(interval_hours))
        logger.info(f"Idea scheduler started (every {interval_hours}h)")


def stop_scheduler():
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("Idea scheduler stopped")
