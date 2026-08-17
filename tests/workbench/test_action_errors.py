"""Tests for actionable errors + quality panel flattening."""

from __future__ import annotations

from cn_social_agent.action_errors import (
    classify_error,
    journal_quality_items,
    presentation_quality_items,
)
from cn_social_agent.cards.quality import journal_depth_report


def test_classify_edge_tts():
    err = classify_error("语音合成失败：cmd failed (1): /opt/homebrew/bin/edge-tts --voice …")
    assert err["code"] == "edge_tts_network"
    assert any(a["id"] == "retry_tts_api" for a in err["actions"])
    assert "edge-tts" in err["reason"] or "TTS" in err["reason"]


def test_classify_llm_json():
    err = classify_error("LLM JSON 解析失败；片段: {\"cover\":")
    assert err["code"] == "llm_json"
    assert any(a["id"] == "switch_model" for a in err["actions"])


def test_classify_missing_scene():
    err = classify_error("RuntimeError: 缺少分镜片段 scene_2.mp4，请先完整渲染一次")
    assert err["code"] == "missing_scene"
    assert any(a["id"] == "rerender_missing" for a in err["actions"])


def test_classify_generate_failed():
    err = classify_error("generate_failed: TimeoutError: timed out")
    assert err["code"] == "generate_failed"


def test_classify_agnes_queue():
    err = classify_error("Agnes video_queue_full: queue is full")
    assert err["code"] == "agnes_queue"


def test_journal_quality_items_from_depth():
    payload = {
        "mode": "journal",
        "cover": {"title": "t", "tags": ["AI"], "marketNote": "热度 9 天 2 万 Star"},
        "frontMatter": {"guide": {"promises": ["a", "b", "c"]}, "toc": [1, 2, 3]},
        "knowledge": [
            {
                "card_kind": "concept",
                "concept": "x",
                "flow": ["启动", "授权", "构建"],
                "diagram": {"type": "pipeline"},
                "evidenceIds": ["e1"],
            },
            {
                "card_kind": "data",
                "metric": "2万",
                "flow": ["热度"],
                "diagram": {"type": "cards"},
                "evidenceIds": ["e2"],
            },
            {
                "card_kind": "compare",
                "compare_left": "A",
                "compare_right": "B",
                "flow": ["对比"],
                "diagram": {"type": "compare"},
            },
            {
                "card_kind": "steps",
                "flow": ["一步", "二步", "三步"],
                "diagram": {"type": "pipeline"},
                "evidenceIds": ["e3"],
            },
            {
                "card_kind": "keypoints",
                "flow": ["要点"],
                "diagram": {"type": "cards"},
            },
        ],
    }
    depth = journal_depth_report(payload, rich_journal=True)
    items = journal_quality_items(depth)
    assert items
    assert all("label" in i and "status" in i for i in items)
    by_id = {i["id"]: i for i in items}
    assert "cards_ge_5" in by_id
    assert by_id["cards_ge_5"]["status"] == "pass"


def test_presentation_quality_items_pending_final():
    content = {
        "ok": False,
        "checks": {
            "depth_ok": True,
            "stage_built": True,
            "a1_confirmed": True,
            "demo_verify_pass": False,
            "narration_timeline_ok": True,
        },
        "verification": {
            "ok": False,
            "declared": 2,
            "passed": 0,
            "failed": 0,
            "pending": 2,
            "unavailable": 0,
            "roles_present": ["demo"],
            "missing_roles": [],
        },
    }
    items = presentation_quality_items(content, final_qc={"path": "", "ok": False, "reasons": ["尚未导入成片"]})
    assert any(i["id"] == "demo_verify_pass" and i["status"] == "fail" for i in items)
    assert any(i["id"] == "final_imported" and i["status"] == "pending" for i in items)
