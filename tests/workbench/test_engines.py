"""Tests for the engine abstraction layer (registry + protocol)."""
from __future__ import annotations

from pathlib import Path

import pytest

from cn_social_agent.video.engines import (
    available_engines,
    get_engine,
    register,
)


class FakeEngine:
    @classmethod
    def configured(cls) -> bool:
        return True

    def __init__(self, **kw):
        self.kw = kw

    async def generate_to_file(self, prompt, dest, **kw):
        return {"path": str(dest)}


def test_agnes_registered_by_default():
    engines = available_engines()
    assert "agnes" in engines


def test_get_engine_returns_class():
    cls = get_engine("agnes")
    assert cls is not None
    assert hasattr(cls, "configured")
    assert hasattr(cls, "generate_to_file") or callable(getattr(cls, "__init__", None))


def test_get_engine_env_fallback(monkeypatch):
    monkeypatch.setenv("WORKBENCH_VIDEO_ENGINE", "agnes")
    cls = get_engine()
    assert cls is not None


def test_get_engine_unknown_returns_none():
    cls = get_engine("nonexistent_engine")
    assert cls is None


def test_register_custom_engine():
    register("custom_fake", FakeEngine)
    cls = get_engine("custom_fake")
    assert cls is FakeEngine
    assert cls.configured() is True


def test_available_engines_includes_registered():
    register("z_fake_for_list_test", FakeEngine)
    assert "z_fake_for_list_test" in available_engines()
