from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .base import ConnectorConfig, ConnectorStatus, IdeaConnector, RawMaterial

logger = logging.getLogger(__name__)


class ConnectorManager:
    def __init__(self):
        self._connectors: dict[str, type[IdeaConnector]] = {}
        self._instances: dict[str, dict[str, IdeaConnector]] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def register(self, connector_class: type[IdeaConnector]) -> None:
        self._connectors[connector_class.id] = connector_class

    def get_connector_class(self, connector_id: str) -> Optional[type[IdeaConnector]]:
        return self._connectors.get(connector_id)

    def list_connector_types(self) -> list[dict[str, Any]]:
        result = []
        for cid, cls in self._connectors.items():
            instance = None
            if self._instances:
                first_user = next(iter(self._instances.values()), {})
                instance = first_user.get(cid)

            result.append({
                "id": cid,
                "name": cls.name,
                "description": cls.description,
                "icon": cls.icon,
                "capabilities": cls.capabilities,
                "status": instance.status.value if instance else "not_configured",
            })
        return result

    def get_or_create(
        self, user_id: str, connector_id: str, config: ConnectorConfig
    ) -> IdeaConnector:
        if user_id not in self._instances:
            self._instances[user_id] = {}

        if connector_id in self._instances[user_id]:
            return self._instances[user_id][connector_id]

        cls = self._connectors.get(connector_id)
        if not cls:
            raise ValueError(f"Unknown connector: {connector_id}")

        instance = cls(config)
        self._instances[user_id][connector_id] = instance
        return instance

    async def fetch_all(self, user_id: str) -> list[RawMaterial]:
        all_materials = []
        user_connectors = self._instances.get(user_id, {})

        for cid, connector in user_connectors.items():
            if not connector.config.enabled:
                continue

            try:
                connector.status = ConnectorStatus.RUNNING
                materials = await connector.fetch()
                all_materials.extend(materials)
                connector.last_sync_at = __import__("datetime").datetime.now()
                connector.sync_count += 1
                connector.status = ConnectorStatus.READY
                logger.info(f"Fetched {len(materials)} items from {cid}")
            except Exception as e:
                connector.status = ConnectorStatus.ERROR
                logger.error(f"Error fetching from {cid}: {e}")

        return all_materials

    async def fetch_connector(
        self, user_id: str, connector_id: str
    ) -> list[RawMaterial]:
        user_connectors = self._instances.get(user_id, {})
        connector = user_connectors.get(connector_id)
        if not connector:
            raise ValueError(f"Connector {connector_id} not configured for user {user_id}")

        connector.status = ConnectorStatus.RUNNING
        try:
            materials = await connector.fetch()
            connector.last_sync_at = __import__("datetime").datetime.now()
            connector.sync_count += 1
            connector.status = ConnectorStatus.READY
            return materials
        except Exception as e:
            connector.status = ConnectorStatus.ERROR
            raise

    async def start_monitoring(
        self, user_id: str, connector_id: str, callback
    ) -> None:
        task_key = f"{user_id}:{connector_id}"
        if task_key in self._tasks:
            return

        user_connectors = self._instances.get(user_id, {})
        connector = user_connectors.get(connector_id)
        if not connector or not connector.capabilities.get("monitor"):
            return

        async def _monitor_loop():
            while True:
                try:
                    materials = await connector.fetch()
                    for m in materials:
                        callback(m)
                except Exception as e:
                    logger.error(f"Monitor error for {connector_id}: {e}")
                await asyncio.sleep(connector.config.interval_ms / 1000)

        self._tasks[task_key] = asyncio.create_task(_monitor_loop())

    async def stop_monitoring(self, user_id: str, connector_id: str) -> None:
        task_key = f"{user_id}:{connector_id}"
        task = self._tasks.pop(task_key, None)
        if task:
            task.cancel()

    def get_user_status(self, user_id: str) -> list[dict[str, Any]]:
        user_connectors = self._instances.get(user_id, {})
        result = []
        for cid, connector in user_connectors.items():
            result.append({
                "connector_id": cid,
                "name": connector.name,
                "status": connector.status.value,
                "enabled": connector.config.enabled,
                "last_sync_at": connector.last_sync_at.isoformat() if connector.last_sync_at else None,
                "sync_count": connector.sync_count,
            })
        return result


manager = ConnectorManager()
