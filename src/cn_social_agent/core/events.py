"""In-process event bus for streaming task progress to the browser.

Task execution is long-running; the UI must show the trace as it happens.
The bus is deliberately dependency-free (asyncio queues + SSE) so it works
without adding a websocket stack, and it is *scoped by stream key*: a
subscriber only ever receives events for streams it was admitted to, which are
keyed by tenant id so one user can never observe another's execution.

Events are also persisted as task steps by the task engine, so a reconnect can
replay history from the database instead of relying on the bus.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """A single execution event."""

    stream: str
    kind: str
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class EventBus:
    """Fan-out bus with per-stream subscriber sets."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[Event]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, stream: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subscribers.setdefault(stream, set()).add(queue)
        return queue

    async def unsubscribe(self, stream: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            peers = self._subscribers.get(stream)
            if peers and queue in peers:
                peers.discard(queue)
            if peers is not None and not peers:
                self._subscribers.pop(stream, None)

    async def publish(self, stream: str, kind: str, message: str = "", **data: Any) -> None:
        event = Event(stream=stream, kind=kind, message=message, data=data)
        async with self._lock:
            peers = list(self._subscribers.get(stream, ()))
        for queue in peers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Slow consumer: drop the oldest event rather than block the run.
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    async def stream(
        self, stream: str, *, idle_timeout: float = 300.0, heartbeat: float = 15.0
    ) -> AsyncIterator[Event]:
        """Yield events for ``stream`` until the client disconnects or idles out."""
        queue = await self.subscribe(stream)
        started = time.time()
        try:
            while True:
                try:
                    yield await asyncio.wait_for(queue.get(), timeout=heartbeat)
                    started = time.time()
                except asyncio.TimeoutError:
                    # Heartbeat keeps proxies from closing an idle connection.
                    yield Event(stream=stream, kind="heartbeat", message="")
                    if idle_timeout and (time.time() - started) >= idle_timeout:
                        return
        finally:
            await self.unsubscribe(stream, queue)


_bus: Optional[EventBus] = None


def bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def task_stream(tenant_id: str, task_id: str) -> str:
    """Stream key — always tenant-qualified so streams cannot collide across users."""
    return f"{tenant_id}:{task_id}"


async def emit(tenant_id: str, task_id: str, kind: str, message: str = "", **data: Any) -> None:
    await bus().publish(task_stream(tenant_id, task_id), kind, message, **data)
