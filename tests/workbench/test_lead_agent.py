"""Lead Agent middleware + mode tests."""

from __future__ import annotations

import asyncio

from cn_social_agent.agent.loop import AgentLoop, MockLLM
from cn_social_agent.agent.middleware import TurnContext, after_turn, before_tool
from cn_social_agent.agent.mode import detect_mode, tools_for_mode
from cn_social_agent.agent.state import apply_write_todos, normalize_agent_state
from cn_social_agent.tools import ToolRegistry, register_builtin_tools


def test_detect_produce_from_keyword():
    assert detect_mode([{"role": "user", "content": "帮我做一条短视频讲 OpenClaw"}]) == "produce"
    assert detect_mode([{"role": "user", "content": "今天天气怎么样"}]) == "simple"
    assert detect_mode([{"role": "user", "content": "扫一下热点榜"}]) == "simple"
    assert detect_mode([{"role": "user", "content": "看看 github.com/foo/bar"}]) == "simple"
    assert detect_mode([{"role": "user", "content": "查一下老龄化数据"}]) == "simple"
    assert detect_mode([{"role": "user", "content": "做成知识卡片讲 OpenClaw"}]) == "produce"


def test_tool_groups():
    assert "propose_short_video" in tools_for_mode("produce")
    assert "propose_short_video" not in tools_for_mode("simple")
    assert "now" in tools_for_mode("simple")


def test_clarify_hard_gate_blocks_propose():
    async def _run():
        tools = ToolRegistry()
        register_builtin_tools(tools)
        ctx = TurnContext(mode="produce", prefs={}, agent_state=normalize_agent_state({}))
        name, args, forced = await before_tool(
            "propose_short_video",
            {"topic": "OpenClaw 入门"},
            ctx,
            tools,
        )
        assert name == "clarify_brief"
        assert forced is not None
        data = forced.data
        assert data.get("clarify") is True
        assert data.get("blocked_propose") is True

        # prefs audience unlocks propose
        ctx.prefs = {"default_audience": "独立开发者"}
        name2, args2, forced2 = await before_tool(
            "propose_short_video",
            {"topic": "OpenClaw 入门"},
            ctx,
            tools,
        )
        assert name2 == "propose_short_video"
        assert forced2 is None
        assert args2.get("audience") == "独立开发者"

        # presentation without audience is blocked
        name3, _args3, forced3 = await before_tool(
            "draft_presentation_content",
            {"topic": "OpenClaw 机制"},
            TurnContext(mode="produce", prefs={}, agent_state=normalize_agent_state({})),
            tools,
        )
        assert name3 == "clarify_brief"
        assert forced3 is not None
        assert forced3.data.get("video_track") == "presentation"

        name4, args4, forced4 = await before_tool(
            "propose_presentation",
            {"topic": "OpenClaw 机制"},
            TurnContext(
                mode="produce",
                prefs={"default_audience": "独立开发者"},
                agent_state=normalize_agent_state({}),
            ),
            tools,
        )
        assert name4 == "propose_presentation"
        assert forced4 is None
        assert args4.get("audience") == "独立开发者"
        assert args4.get("aspect") == "9:16"

    asyncio.run(_run())


def test_present_auto_when_project_bound():
    async def _run():
        tools = ToolRegistry()
        register_builtin_tools(tools)
        ctx = TurnContext(
            mode="produce",
            prefs={"default_audience": "开发者"},
            agent_state=normalize_agent_state({"active_project_id": "proj-1", "mode": "produce"}),
            tool_trace=[
                {
                    "name": "propose_short_video",
                    "arguments": {"topic": "T", "audience": "开发者"},
                    "result": {
                        "success": True,
                        "data": {"ok": True, "ready": True, "topic": "T"},
                        "error": None,
                        "execution_time": 0,
                    },
                }
            ],
        )
        ctx = await after_turn(ctx, tools)
        names = [t["name"] for t in ctx.tool_trace]
        assert "present_video_artifact" in names
        assert ctx.agent_state.get("needs_present") is False

    asyncio.run(_run())


def test_write_todos_apply():
    st = apply_write_todos(
        {},
        [{"id": "topic", "status": "done", "detail": "OpenClaw"}],
        active_project_id="",
    )
    assert st["mode"] == "produce"
    assert st["todos"][0]["status"] == "done"


def test_simple_mode_no_coach_tools_filtered():
    async def _run():
        tools = ToolRegistry()
        register_builtin_tools(tools)
        loop = AgentLoop(MockLLM(), tools, max_tool_rounds=3)
        reply = await loop.run(
            [{"role": "user", "content": "你好"}],
            system_prompt="",
        )
        assert reply.mode == "simple"
        # Mock returns text only — fine
        assert reply.content.startswith("[mock]")

    asyncio.run(_run())
