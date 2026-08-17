from __future__ import annotations

import uuid

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from cn_social_agent.api import create_app
from cn_social_agent.tools import ToolRegistry, register_builtin_tools
from cn_social_agent.agent import AgentLoop, MockLLM


@pytest.mark.asyncio
async def test_builtin_now_tool():
    reg = ToolRegistry()
    register_builtin_tools(reg)
    result = await reg.execute("now", {})
    assert result.success
    assert "iso" in result.data


@pytest.mark.asyncio
async def test_agent_mock_reply():
    reg = ToolRegistry()
    register_builtin_tools(reg)
    agent = AgentLoop(llm=MockLLM(), tools=reg)
    reply = await agent.run([{"role": "user", "content": "hello"}])
    assert "hello" in reply.content


@pytest.mark.asyncio
async def test_agent_tool_round():
    reg = ToolRegistry()
    register_builtin_tools(reg)
    agent = AgentLoop(llm=MockLLM(), tools=reg)
    reply = await agent.run([{"role": "user", "content": "/tool now"}])
    assert reply.tool_calls
    assert reply.tool_calls[0]["name"] == "now"


@pytest.mark.asyncio
async def test_health_and_auth_flow(monkeypatch):
    monkeypatch.setenv("WORKBENCH_STORE", "memory")
    monkeypatch.setenv("WORKBENCH_LLM", "mock")
    app = create_app()
    async with TestClient(TestServer(app)) as client:
        health = await client.get("/health")
        assert health.status == 200
        body = await health.json()
        assert body["status"] == "ok"
        assert body["store"] == "memory"
        assert body["llm"] == "mock"

        # Unique email: auth may back onto persistent InsForge, where a
        # fixed address 409s on the second run.
        email = f"t-{uuid.uuid4().hex[:10]}@example.com"
        reg = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "secret123"},
        )
        assert reg.status == 200
        token = (await reg.json())["accessToken"]

        me = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert me.status == 200

        sess = await client.post(
            "/api/sessions",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert sess.status == 201
        sid = (await sess.json())["id"]

        chat = await client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"session_id": sid, "content": "ping"},
        )
        assert chat.status == 200
        data = await chat.json()
        assert "ping" in data["message"]["content"]
