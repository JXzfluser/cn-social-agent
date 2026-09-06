"""Engine abstraction layer for scene video generation.

Per design doc 20260822: registry + per-scene engine override from scene meta,
env var default fallback. Agnes is the default and currently only engine.
"""
from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

from pathlib import Path


@runtime_checkable
class Engine(Protocol):
    @classmethod
    def configured(cls) -> bool: ...

    def __init__(self, **kw: Any) -> None: ...

    async def generate_to_file(
        self,
        prompt: str,
        dest: Path,
        *,
        width: int = 768,
        height: int = 1344,
        num_frames: int = 121,
        frame_rate: int = 24,
        on_progress: Any = None,
    ) -> dict[str, Any]: ...


_ENGINES: dict[str, type[Engine]] = {}


def register(name: str, engine_cls: type[Engine]) -> None:
    _ENGINES[name] = engine_cls


def get_engine(name: str | None = None) -> type[Engine] | None:
    resolved = name or os.getenv("WORKBENCH_VIDEO_ENGINE") or "agnes"
    return _ENGINES.get(resolved)


def available_engines() -> list[str]:
    return sorted(_ENGINES.keys())


def _register_defaults() -> None:
    try:
        from cn_social_agent.video.agnes_client import AgnesVideoClient
        register("agnes", AgnesVideoClient)  # type: ignore[arg-type]
    except ImportError:
        pass


_register_defaults()
