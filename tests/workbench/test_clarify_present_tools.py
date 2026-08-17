import asyncio

from cn_social_agent.tools.builtin import tool_clarify_brief, tool_present_video_artifact


def test_clarify_brief():
    out = asyncio.run(
        tool_clarify_brief(question="受众是谁？", topic="OpenClaw", need="audience|scene")
    )
    assert out["clarify"] is True
    assert out["ready"] is False
    assert "audience" in " ".join(out["need"])


def test_clarify_brief_track_need():
    out = asyncio.run(
        tool_clarify_brief(
            question="口播还是讲解？",
            topic="OpenClaw",
            need="track|audience",
            video_track="讲解演示",
        )
    )
    assert "track" in out["need"]
    assert out["video_track"] == "presentation"


def test_present_requires_project():
    bad = asyncio.run(tool_present_video_artifact(project_id=""))
    assert bad["ok"] is False
    good = asyncio.run(
        tool_present_video_artifact(project_id="abc", note="看这里", topic="T")
    )
    assert good["present"] is True
    assert good["project_id"] == "abc"
