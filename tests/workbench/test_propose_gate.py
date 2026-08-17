import asyncio

from cn_social_agent.tools.builtin import tool_propose_short_video


def test_propose_requires_audience_or_scene():
    out = asyncio.run(
        tool_propose_short_video(topic="OpenClaw 入门", selling_points="三步上手")
    )
    assert out["ok"] is True
    assert out["ready"] is False
    assert "audience|scene" in (out.get("need") or [])


def test_propose_ready_with_audience():
    out = asyncio.run(
        tool_propose_short_video(
            topic="OpenClaw 入门",
            audience="独立开发者",
        )
    )
    assert out["ready"] is True
    assert out.get("need") == []
    assert out.get("workshop_mode") == "koubo"
    assert out.get("video_track") == "koubo"
