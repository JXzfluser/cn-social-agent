"""Topic key + asset aggregation unit tests."""

from __future__ import annotations

from cn_social_agent.knowledge.assets import group_topic_assets, journal_item_from_row
from cn_social_agent.knowledge.topic_key import topic_key
from cn_social_agent.video.pipeline import encode_script_bundle


def test_topic_key_strips_noise_and_case():
    assert topic_key("关于 DeepSeek 入门") == topic_key("deepseek")
    assert topic_key("一文读懂 LangChain 指南") == topic_key("langchain")
    assert topic_key("DeepSeek Agent 框架") == topic_key("DeepSeek Agent")
    assert topic_key("") == ""


def test_group_merges_journal_and_video():
    journals = [
        {
            "id": "h1",
            "ts": "2026-08-16T10:00:00",
            "roles": ["DeepSeek Agent"],
            "category": "hiring_insight",
            "mode": "journal",
            "cover": {"title": "DeepSeek Agent 能力图谱"},
            "evidencePack": {"count": 12, "evidences": []},
        }
    ]
    script = encode_script_bundle(
        {
            "full_script": "旁白",
            "content_angle": "intro",
            "delivery_level": "l0",
        }
    )
    videos = [
        {
            "id": "v1",
            "topic": "DeepSeek Agent 框架",
            "title": "口播草稿",
            "status": "done",
            "script": script,
            "updated_at": "2026-08-16T11:00:00",
            "output_path": "/tmp/x.mp4",
        }
    ]
    topics = group_topic_assets(journals=journals, videos=videos)
    assert len(topics) == 1
    t = topics[0]
    assert t["journal_count"] == 1
    assert t["video_count"] == 1
    assert t["evidence_count"] == 12
    assert "journal" in t["kinds"]
    assert "koubo" in t["kinds"]
    assert t["journals"][0]["pack_id"] == "h1"


def test_journal_item_requires_id_and_topic():
    assert journal_item_from_row({"roles": ["x"]}) is None
    assert journal_item_from_row({"id": "h", "roles": []}) is None
    item = journal_item_from_row({"id": "h", "roles": ["OpenClaw"], "ts": "t"})
    assert item and item["topic_key"] == topic_key("OpenClaw")


def test_recent_topics_seed_empty_shell():
    topics = group_topic_assets(
        journals=[], videos=[], recent_topics=["Harness 框架"]
    )
    assert len(topics) == 1
    assert topics[0]["journal_count"] == 0
    assert topics[0]["topic_key"] == topic_key("Harness 框架")


def test_assets_mode_ui_hooks():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    html = (root / "src/cn_social_agent/workbench/index.html").read_text(encoding="utf-8")
    assert 'data-mode="assets"' in html
    assert 'id="viewAssets"' in html
    assert "refreshTopicAssets" in html
    assert "/api/topic-assets" in html


def test_push_recipe_prefs():
    from cn_social_agent.api.prefs import merge_prefs, normalize_prefs

    p = merge_prefs(
        {},
        {
            "push_recipe": {
                "content_angle": "compare",
                "audience": "独立开发者",
                "scene_setting": "选型纠结",
            }
        },
    )
    assert p["recent_recipes"][0]["content_angle"] == "compare"
    assert normalize_prefs(p)["recent_recipes"][0]["audience"] == "独立开发者"
