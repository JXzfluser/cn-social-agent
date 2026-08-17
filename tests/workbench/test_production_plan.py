"""Unit tests for production plan derivation."""

from __future__ import annotations

from cn_social_agent.video.plan import build_production_plan
from cn_social_agent.video.pipeline import encode_script_bundle


def _meta_script(**meta) -> str:
    data = {
        "full_script": meta.pop("full_script", "旁白"),
        "cover_hook": "",
        "hashtags": [],
        "cta": "",
        "audience": "",
        "scene_setting": "",
        "platform": "抖音",
        "bg_theme": "night",
        "motion": "kenburns",
        "render_mode": "local",
        "content_angle": "",
        "delivery_level": "",
        "fail_reason": "",
        **meta,
    }
    return encode_script_bundle(data)


def test_empty_project_topic_active():
    plan = build_production_plan({"topic": "", "script": "", "status": "draft"}, [])
    assert plan["total"] == 6
    by_id = {s["id"]: s for s in plan["steps"]}
    assert by_id["topic"]["status"] == "active"
    assert by_id["script"]["status"] == "pending"
    assert plan["done_count"] == 0


def test_topic_only_then_angle_active():
    plan = build_production_plan({"topic": "OpenClaw 入门", "script": "", "status": "draft"}, [])
    by_id = {s["id"]: s for s in plan["steps"]}
    assert by_id["topic"]["status"] == "done"
    assert by_id["angle"]["status"] == "active"


def test_scenes_mark_script_pending_until_confirmed():
    script = _meta_script(
        content_angle="intro",
        audience="独立开发者",
        scene_setting="想装又怕踩坑",
        storyboard_confirmed=False,
    )
    plan = build_production_plan(
        {"topic": "OpenClaw", "script": script, "status": "draft"},
        [{"id": "1", "content": "钩子"}, {"id": "2", "content": "步骤"}],
    )
    by_id = {s["id"]: s for s in plan["steps"]}
    assert by_id["script"]["status"] == "active"
    assert "待确认" in by_id["script"]["detail"]
    assert by_id["l0"]["status"] == "pending"
    assert "确认" in by_id["l0"]["detail"]
    assert plan["done_count"] == 3


def test_scenes_mark_script_done():
    script = _meta_script(
        content_angle="intro",
        audience="独立开发者",
        scene_setting="想装又怕踩坑",
        storyboard_confirmed=True,
    )
    plan = build_production_plan(
        {"topic": "OpenClaw", "script": script, "status": "draft"},
        [{"id": "1", "content": "钩子"}, {"id": "2", "content": "步骤"}],
    )
    by_id = {s["id"]: s for s in plan["steps"]}
    assert by_id["topic"]["status"] == "done"
    assert by_id["angle"]["status"] == "done"
    assert by_id["brief"]["status"] == "done"
    assert by_id["script"]["status"] == "done"
    assert by_id["script"]["detail"] == "2 镜·已确认"
    assert by_id["l0"]["status"] == "active"
    assert plan["done_count"] == 4


def test_l0_done_progress():
    script = _meta_script(
        content_angle="intro",
        audience="开发者",
        delivery_level="l0",
        storyboard_confirmed=True,
    )
    plan = build_production_plan(
        {
            "topic": "T",
            "script": script,
            "status": "done",
            "output_path": "/tmp/x.mp4",
        },
        [{"id": "1"}],
    )
    by_id = {s["id"]: s for s in plan["steps"]}
    assert by_id["l0"]["status"] == "done"
    assert by_id["l1"]["status"] == "active"
    assert plan["progress_label"] == "5/6"


def test_l1_done_all():
    script = _meta_script(
        content_angle="compare",
        audience="a",
        delivery_level="l1",
        storyboard_confirmed=True,
    )
    plan = build_production_plan(
        {"topic": "T", "script": script, "status": "done", "output_path": "/tmp/x.mp4"},
        [{"id": "1"}],
    )
    assert plan["done_count"] == 6
    assert all(s["status"] == "done" for s in plan["steps"])


def test_angle_detail_uses_chinese_label():
    script = _meta_script(content_angle="deep_analysis", audience="a")
    plan = build_production_plan(
        {"topic": "T", "script": script, "status": "draft"}, []
    )
    by_id = {s["id"]: s for s in plan["steps"]}
    assert by_id["angle"]["detail"] == "深度分析"


def test_clarify_card_offers_angle_choice():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    html = (root / "src/cn_social_agent/workbench/index.html").read_text(encoding="utf-8")
    # 澄清卡里可以选视频类型，且制片进度的「类型」格子可点击
    assert 'data-role="angle"' in html
    assert "default_content_angle: angle" in html
    assert 'data-step="angle"' in html


def test_l0_failed_shows_reason():
    script = _meta_script(
        content_angle="intro",
        audience="a",
        fail_reason="generate_failed: x",
        storyboard_confirmed=True,
    )
    plan = build_production_plan(
        {"topic": "T", "script": script, "status": "failed"},
        [{"id": "1"}],
        job={"status": "failed", "delivery_level": "l0", "fail_reason": "boom"},
    )
    by_id = {s["id"]: s for s in plan["steps"]}
    assert by_id["l0"]["status"] == "failed"
    assert "boom" in by_id["l0"]["detail"]
