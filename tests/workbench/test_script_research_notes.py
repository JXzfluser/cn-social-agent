"""generate_script consumes research_notes (P1-2)."""

from __future__ import annotations

import pytest


class RecordingLLM:
    def __init__(self):
        self.messages: list[list[dict]] = []

    async def chat_completion(self, messages, **kwargs):
        self.messages.append(messages)
        return {"choices": [{"message": {"content": "not json"}}]}


@pytest.mark.asyncio
async def test_generate_script_injects_research_notes():
    from cn_social_agent.video.pipeline import generate_script

    llm = RecordingLLM()
    await generate_script(
        llm,
        topic="LangGraph 入门",
        seconds=60,
        research_notes="LangGraph 1.0 默认图编排，checkpoints 可持久化",
    )
    prompt = llm.messages[0][0]["content"]
    assert "调研摘录" in prompt
    assert "LangGraph 1.0 默认图编排，checkpoints 可持久化" in prompt


@pytest.mark.asyncio
async def test_generate_script_without_notes_skips_section():
    from cn_social_agent.video.pipeline import generate_script

    llm = RecordingLLM()
    await generate_script(llm, topic="LangGraph 入门", seconds=60)
    prompt = llm.messages[0][0]["content"]
    assert "调研摘录" not in prompt
