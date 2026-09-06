from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ConnectorStatus(str, Enum):
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class RawMaterial:
    id: str
    connector_id: str
    source: str
    title: str
    url: Optional[str] = None
    summary: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    heat: int = 0
    raw_data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ConnectorConfig:
    user_id: str
    enabled: bool = True
    interval_ms: int = 3600000
    max_items: int = 50
    keywords: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


class IdeaConnector(ABC):
    id: str
    name: str
    description: str
    icon: str

    capabilities: dict[str, bool] = {
        "source": True,
        "monitor": False,
        "realtime": False,
    }

    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.status = ConnectorStatus.READY
        self.last_sync_at: Optional[datetime] = None
        self.sync_count: int = 0

    @abstractmethod
    async def fetch(self) -> list[RawMaterial]:
        ...

    async def monitor(self, callback) -> None:
        raise NotImplementedError(f"{self.id} does not support monitoring")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "status": self.status.value,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "sync_count": self.sync_count,
            "capabilities": self.capabilities,
        }
