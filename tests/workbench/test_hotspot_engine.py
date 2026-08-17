import pytest

from cn_social_agent.tools.hotspot_engine import (
    assign_domains,
    attach_local_assets,
    build_why,
    dedupe_by_topic_key,
    enrich_item,
    heat_norm,
    infer_freshness,
)


def test_heat_norm_monotonic():
    assert heat_norm(0, source="hn") < heat_norm(100, source="hn")
    assert 0 <= heat_norm(50, source="github") <= 100


def test_assign_domains_ai():
    assert "ai" in assign_domains("New LLM Agent framework", "")


def test_dedupe_keeps_higher_score():
    a = {"title": "Foo Bar", "full_name": "Foo Bar", "score": 40, "source": "hn"}
    b = {"title": "Foo Bar", "full_name": "Foo Bar", "score": 80, "source": "github"}
    out = dedupe_by_topic_key([a, b])
    assert len(out) == 1
    assert out[0]["score"] == 80


def test_build_why_github():
    why = build_why({"source": "github", "language": "Python", "local_assets": None})
    assert "高星" in why or "适合" in why


def test_build_why_with_assets():
    why = build_why(
        {
            "source": "hn",
            "local_assets": {"journal_count": 1, "video_count": 0},
        }
    )
    assert "本地已有资产" in why


@pytest.mark.asyncio
async def test_attach_local_assets_rebuilds_why(monkeypatch):
    async def fake_lookup(query, limit=3):
        assert query
        return {
            "ok": True,
            "hits": [
                {
                    "topic_key": "llm-agent",
                    "topic": "LLM Agent",
                    "journal_count": 2,
                    "video_count": 1,
                }
            ],
            "hint": "本地已有相关主题资产",
        }

    monkeypatch.setattr(
        "cn_social_agent.knowledge.assets.lookup_local_assets",
        fake_lookup,
    )
    board = [
        {
            "source": "hn",
            "title": "LLM Agent framework",
            "topic_key": "llm-agent",
            "why": "社区热议 · 适合观点/对比角",
        }
    ]
    out = await attach_local_assets(board)
    assert len(out) == 1
    assert out[0]["local_assets"]["journal_count"] == 2
    assert out[0]["local_assets"]["video_count"] == 1
    assert "本地已有资产" in out[0]["why"]


@pytest.mark.asyncio
async def test_attach_local_assets_skips_empty_hits(monkeypatch):
    async def fake_lookup(query, limit=3):
        return {"ok": True, "hits": [], "hint": "暂无"}

    monkeypatch.setattr(
        "cn_social_agent.knowledge.assets.lookup_local_assets",
        fake_lookup,
    )
    board = [{"source": "hn", "title": "No match", "topic_key": "no-match", "why": "社区热议 · 适合观点/对比角"}]
    out = await attach_local_assets(board)
    assert out[0].get("local_assets") is None or "local_assets" not in out[0]
    assert "本地已有资产" not in out[0]["why"]


def test_infer_freshness_by_source():
    assert infer_freshness("hn") == "hot"
    assert infer_freshness("v2ex") == "hot"
    assert infer_freshness("github") == "rising"
    assert infer_freshness("devto") == "steady"


def test_enrich_item_infers_freshness():
    assert enrich_item({"source": "github", "title": "Foo"})["freshness"] == "rising"
    assert enrich_item({"source": "devto", "title": "Bar"})["freshness"] == "steady"
    assert enrich_item({"source": "github", "title": "Baz", "freshness": "hot"})["freshness"] == "hot"


def test_enrich_item_sets_topic_key_and_score():
    item = {
        "source": "hn",
        "full_name": "New LLM Agent framework",
        "stars": 120,
        "description": "A framework for building agents",
    }
    out = enrich_item(item)
    assert out.get("topic_key")
    assert isinstance(out.get("score"), (int, float))
    assert out["score"] > 0
    assert out.get("why")
    assert out.get("domains")


def test_hotspots_module_wires_engine():
    """Smoke: scan tool imports engine helpers and accepts domain."""
    import inspect

    from cn_social_agent.tools.hotspots import tool_scan_hotspot_board

    sig = inspect.signature(tool_scan_hotspot_board)
    assert "domain" in sig.parameters
    assert sig.parameters["domain"].default == "all"
