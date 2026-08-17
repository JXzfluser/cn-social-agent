"""Platform publisher registry."""

from __future__ import annotations

from typing import Any

from cn_social_agent.platforms.mock import MockPublisher

_REGISTRY: dict[str, type] = {"mock": MockPublisher}


def register_publisher(name: str, cls: type) -> None:
    _REGISTRY[(name or "").strip().lower()] = cls


def get_publisher(name: str) -> Any:
    key = (name or "").strip().lower()
    cls = _REGISTRY.get(key)
    if not cls:
        raise KeyError(f"unknown platform: {name}")
    return cls()


def list_platforms() -> list[str]:
    return sorted(_REGISTRY.keys())


def _register_builtins() -> None:
    try:
        from cn_social_agent.platforms.weixin.publisher import WeixinPublisher

        register_publisher("weixin", WeixinPublisher)
    except Exception:  # noqa: BLE001
        pass
    try:
        from cn_social_agent.platforms.toutiao.publisher import ToutiaoPublisher

        register_publisher("toutiao", ToutiaoPublisher)
    except Exception:  # noqa: BLE001
        pass
    try:
        from cn_social_agent.platforms.douyin.publisher import DouyinPublisher

        register_publisher("douyin", DouyinPublisher)
    except Exception:  # noqa: BLE001
        pass
    try:
        from cn_social_agent.platforms.xiaohongshu.publisher import XiaohongshuPublisher

        register_publisher("xiaohongshu", XiaohongshuPublisher)
    except Exception:  # noqa: BLE001
        pass


_register_builtins()
