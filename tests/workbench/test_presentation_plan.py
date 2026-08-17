"""Unit tests for presentation production plan."""

from __future__ import annotations

from cn_social_agent.video.plan import build_production_plan
from cn_social_agent.video.pipeline import encode_script_bundle
from cn_social_agent.video.presentation import STAGE_SIZES, obs_checklist


def test_stage_sizes():
    assert STAGE_SIZES["16:9"] == (1920, 1080)
    assert STAGE_SIZES["9:16"] == (1080, 1920)


def test_presentation_plan_topic_active():
    script = encode_script_bundle(
        {"full_script": "", "video_type": "presentation", "aspect": "16:9"}
    )
    plan = build_production_plan(
        {"topic": "", "script": script, "status": "draft", "video_type": "presentation"},
        [],
    )
    assert plan["track"] == "presentation"
    assert plan["total"] == 6
    by = {s["id"]: s for s in plan["steps"]}
    assert list(by) == ["topic", "outline", "build", "audio", "record", "publish"]
    assert by["topic"]["status"] == "active"


def test_presentation_plan_after_a1():
    script = encode_script_bundle(
        {
            "full_script": "口播",
            "video_type": "presentation",
            "aspect": "9:16",
            "theme": "desk",
            "outline": "ch1...",
            "checkpoints": {"a1": {"confirmed": True}},
        }
    )
    plan = build_production_plan(
        {
            "topic": "Harness 实践",
            "script": script,
            "status": "draft",
            "video_type": "presentation",
        },
        [],
    )
    by = {s["id"]: s for s in plan["steps"]}
    assert by["topic"]["status"] == "done"
    assert by["outline"]["status"] == "done"
    assert by["build"]["status"] == "active"


def test_obs_checklist_aspect():
    c = obs_checklist(aspect="9:16", preview_url="http://x/?auto=1")
    assert c["width"] == 1080 and c["height"] == 1920
    assert "?auto=1" in c["preview_url"]


def test_koubo_plan_still_has_track():
    plan = build_production_plan({"topic": "x", "script": "", "status": "draft"}, [])
    assert plan.get("track") == "koubo"
    assert plan["total"] == 6


def test_is_presentation_prefers_meta():
    from cn_social_agent.video.presentation import is_presentation
    from cn_social_agent.video.pipeline import encode_script_bundle
    script = encode_script_bundle({"full_script": "x", "video_type": "presentation"})
    assert is_presentation({"video_type": "口播", "script": script})
