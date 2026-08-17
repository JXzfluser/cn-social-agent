"""Tests for Fast/Strong chat model router."""

from cn_social_agent.llm.router import (
    pick_default_fast,
    pick_default_strong,
    resolve_chat_model,
)


def test_pick_defaults():
    models = ["agnes-1.5-flash", "agnes-2.0-flash", "agnes-2.5-flash", "agnes-2.5-pro"]
    assert "1.5" in pick_default_fast(models) or "flash" in pick_default_fast(models)
    assert "pro" in pick_default_strong(models) or "2.5" in pick_default_strong(models)


def test_resolve_override_wins():
    r = resolve_chat_model(
        agent_mode="produce",
        prefs={"llm_route": "smart"},
        available_models=["a", "b"],
        body_model="custom-x",
    )
    assert r["tier"] == "override"
    assert r["model"] == "custom-x"


def test_resolve_smart_tiers():
    models = ["agnes-1.5-flash", "agnes-2.5-flash"]
    fast = resolve_chat_model(
        agent_mode="simple",
        prefs={"llm_route": "smart"},
        available_models=models,
        default_model="agnes-2.0-flash",
    )
    strong = resolve_chat_model(
        agent_mode="produce",
        prefs={"llm_route": "smart"},
        available_models=models,
        default_model="agnes-2.0-flash",
    )
    assert fast["tier"] == "fast"
    assert strong["tier"] == "strong"
    assert fast["model"]
    assert strong["model"]


def test_resolve_fixed():
    r = resolve_chat_model(
        agent_mode="produce",
        prefs={"llm_route": "fixed", "llm_model": "pinned-model"},
        available_models=["a", "b"],
    )
    assert r["tier"] == "fixed"
    assert r["model"] == "pinned-model"


def test_agnes_filters_non_chat():
    from cn_social_agent.llm.agnes import AgnesLLM

    assert AgnesLLM._is_chat_model_id("agnes-2.5-flash")
    assert not AgnesLLM._is_chat_model_id("agnes-image-2.1-flash")
    assert not AgnesLLM._is_chat_model_id("agnes-video-v2.0")
