"""Content automations (S3)."""

from __future__ import annotations

import pytest


def test_recipes_catalog():
    from cn_social_agent.content.automations import RECIPES, list_recipes

    ids = {r["id"] for r in RECIPES}
    assert "daily_hotspot_candidates" in ids
    assert "handoff_seed_research" in ids
    assert "quality_pass_mark_export" in ids
    rows = list_recipes({})
    handoff = next(r for r in rows if r["id"] == "handoff_seed_research")
    assert handoff["enabled"] is True
    daily = next(r for r in rows if r["id"] == "daily_hotspot_candidates")
    assert daily["enabled"] is False


def test_apply_automation_patch():
    from cn_social_agent.content.automations import apply_automation_patch, is_automation_enabled

    frag = apply_automation_patch({}, recipe_id="daily_hotspot_candidates", enabled=True)
    assert frag["automations_enabled"]["daily_hotspot_candidates"] is True
    assert is_automation_enabled(frag, "daily_hotspot_candidates") is True
    assert is_automation_enabled(frag, "handoff_seed_research") is True


def test_prefs_normalize_keeps_automations():
    from cn_social_agent.api.prefs import normalize_prefs

    p = normalize_prefs(
        {
            "automations_enabled": {"handoff_seed_research": False, "daily_hotspot_candidates": True},
        }
    )
    assert p["automations_enabled"]["handoff_seed_research"] is False
    assert p["automations_enabled"]["daily_hotspot_candidates"] is True
    assert p["automations_enabled"]["quality_pass_mark_export"] is True


@pytest.mark.asyncio
async def test_run_daily_dry_run(monkeypatch):
    from cn_social_agent.content import automations as auto

    async def fake_scan(**kwargs):
        return {
            "board": [
                {
                    "title": "示例开源工具",
                    "url": "https://example.com/x",
                    "source": "hn",
                    "why": "热度高",
                    "topic_key": "demo",
                }
            ],
            "hint": "",
        }

    monkeypatch.setattr(
        "cn_social_agent.tools.hotspots.tool_scan_hotspot_board",
        fake_scan,
    )

    out = await auto.run_daily_hotspot_candidates(
        user_id="u1",
        prefs={
            "connectors_enabled": {"hotspot_board": True},
            "hotspot_sources_enabled": {"hn": True},
        },
        dry_run=True,
        per_page=3,
    )
    assert out["ok"] is True
    assert out["dry_run"] is True
    assert out["count"] == 1
    assert out["created"][0]["topic"] == "示例开源工具"


@pytest.mark.asyncio
async def test_run_recipe_records_prefs_patch(monkeypatch):
    from cn_social_agent.content import automations as auto

    async def fake_daily(**kwargs):
        return {"ok": True, "created": [], "count": 0, "hint": "empty"}

    monkeypatch.setattr(auto, "run_daily_hotspot_candidates", fake_daily)
    out = await auto.run_recipe(
        "daily_hotspot_candidates",
        user_id="u1",
        prefs={},
        dry_run=True,
    )
    assert out["ok"] is True
    assert "prefs_patch" in out
    assert "daily_hotspot_candidates" in out["prefs_patch"]["automation_last_run"]
    assert out["prefs_patch"]["automation_runs"][0]["recipe_id"] == "daily_hotspot_candidates"


def test_hard_gate_no_publish_actions():
    from cn_social_agent.content.automations import RECIPES

    for r in RECIPES:
        actions = " ".join(r.get("actions") or [])
        assert "publish" not in actions.lower()
