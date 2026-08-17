"""A3: local-first topic asset lookup for Agent."""

from __future__ import annotations

import pytest

from cn_social_agent.knowledge.assets import match_topic_assets, summarize_asset_hit
from cn_social_agent.knowledge.topic_key import topic_key
from cn_social_agent.tools.context import reset_tool_context, set_tool_context
from cn_social_agent.tools.builtin import tool_lookup_topic_assets, tool_propose_knowledge_cards


def test_match_topic_assets_ranks_exact_and_substring():
    topics = [
        {
            "topic_key": topic_key("DeepSeek Agent"),
            "topic": "DeepSeek Agent",
            "journal_count": 1,
            "video_count": 0,
            "evidence_count": 8,
            "kinds": ["journal"],
            "journals": [{"id": "h1", "pack_id": "h1"}],
            "videos": [],
            "latest_ts": "2026-08-16T10:00:00",
        },
        {
            "topic_key": topic_key("LangChain"),
            "topic": "LangChain",
            "journal_count": 0,
            "video_count": 1,
            "evidence_count": 0,
            "kinds": ["koubo"],
            "journals": [],
            "videos": [{"id": "v1"}],
            "latest_ts": "2026-08-15T10:00:00",
        },
    ]
    hits = match_topic_assets(topics, "DeepSeek Agent 框架", limit=5)
    assert hits and hits[0]["topic_key"] == topic_key("DeepSeek Agent")
    assert summarize_asset_hit(hits[0])["latest_pack_id"] == "h1"


@pytest.mark.asyncio
async def test_lookup_tool_uses_context(monkeypatch):
    async def fake_gather(**kwargs):
        assert kwargs["user_id"] == "u1"
        return [
            {
                "topic_key": topic_key("OpenClaw"),
                "topic": "OpenClaw",
                "journal_count": 1,
                "video_count": 0,
                "evidence_count": 3,
                "kinds": ["journal"],
                "journals": [{"id": "h2", "pack_id": "h2"}],
                "videos": [],
                "latest_ts": "t",
            }
        ]

    monkeypatch.setattr(
        "cn_social_agent.knowledge.assets.gather_topic_assets_for_user",
        fake_gather,
    )
    token = set_tool_context(user_id="u1", email="a@b.c", prefs={}, store_mode="memory")
    try:
        out = await tool_lookup_topic_assets(topic="OpenClaw")
    finally:
        reset_tool_context(token)
    assert out["ok"] is True
    assert out["hits"]
    assert out["present_topic_assets"] is True


@pytest.mark.asyncio
async def test_propose_cards_attaches_local_assets(monkeypatch):
    async def fake_lookup(query, limit=5):
        return {
            "ok": True,
            "hits": [
                {
                    "topic_key": "x",
                    "topic": "X",
                    "journal_count": 1,
                    "video_count": 0,
                    "evidence_count": 2,
                    "latest_pack_id": "p1",
                }
            ],
            "hint": "本地已有",
        }

    monkeypatch.setattr(
        "cn_social_agent.knowledge.assets.lookup_local_assets",
        fake_lookup,
    )
    out = await tool_propose_knowledge_cards(topic="X", roles="工程师")
    assert out["local_assets"]
    assert out["present_topic_assets"] is True


def test_lookup_in_tool_modes():
    from cn_social_agent.agent.mode import PRODUCE_TOOLS, RESEARCH_TOOLS

    assert "lookup_topic_assets" in PRODUCE_TOOLS
    assert "lookup_topic_assets" in RESEARCH_TOOLS


def test_ui_handles_lookup_card():
    from pathlib import Path

    html = (
        Path(__file__).resolve().parents[2]
        / "src/cn_social_agent/workbench/index.html"
    ).read_text(encoding="utf-8")
    assert "function appendTopicAssetsCard" in html
    assert "lookup_topic_assets" in html
