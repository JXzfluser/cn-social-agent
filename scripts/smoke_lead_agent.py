#!/usr/bin/env python3
"""Smoke: Lead Agent clarify hard-gate + agent_state on chat (memory store)."""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure src on path when run as script
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cn_social_agent.agent.loop import AgentLoop
from cn_social_agent.agent.middleware import TurnContext, before_tool
from cn_social_agent.agent.mode import detect_mode
from cn_social_agent.agent.state import normalize_agent_state
from cn_social_agent.tools import ToolRegistry, register_builtin_tools


class ProposeLLM:
    """Always tries to propose without audience/scene."""

    async def chat_completion(self, messages, model="", **kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {
                                    "name": "propose_short_video",
                                    "arguments": '{"topic":"OpenClaw 入门"}',
                                },
                            }
                        ],
                    }
                }
            ]
        }


class FollowUpLLM:
    """Second round: text reply after clarify."""

    def __init__(self) -> None:
        self.n = 0

    async def chat_completion(self, messages, model="", **kwargs):
        self.n += 1
        if self.n == 1:
            return await ProposeLLM().chat_completion(messages, model=model, **kwargs)
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "好的，先告诉我受众或场景。",
                    }
                }
            ]
        }


async def main() -> int:
    assert detect_mode([{"role": "user", "content": "帮我做短视频"}]) == "produce"
    tools = ToolRegistry()
    register_builtin_tools(tools)
    assert any(t["name"] == "write_todos" for t in tools.list_tools())

    ctx = TurnContext(mode="produce", prefs={}, agent_state=normalize_agent_state({}))
    name, _args, forced = await before_tool(
        "propose_short_video", {"topic": "X"}, ctx, tools
    )
    assert name == "clarify_brief" and forced and forced.data.get("blocked_propose")
    print("OK clarify hard-gate")

    loop = AgentLoop(FollowUpLLM(), tools)
    reply = await loop.run(
        [{"role": "user", "content": "帮我做一条短视频讲 OpenClaw"}],
        prefs={},
        agent_state={},
    )
    names = [t["name"] for t in reply.tool_calls]
    assert "clarify_brief" in names, names
    assert reply.mode == "produce"
    assert reply.clarify or reply.agent_state.get("last_clarify")
    print("OK lead loop gated propose → clarify", names)
    print("agent_state.mode", reply.agent_state.get("mode"))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
