"""参考资料库 E2E：上传 → 列表 → 读取 → 删除 → 按用户隔离。

PYTHONPATH=src .venv/bin/python -m pytest tests/nexus/test_library.py -q
"""

from __future__ import annotations

import os
import shutil

os.environ.setdefault("WORKBENCH_AUTH", "memory")
os.environ.setdefault("WORKBENCH_STORE", "memory")
os.environ.setdefault("LIBRARY_DATA_DIR", os.path.join(os.path.dirname(__file__), "_tmp_library"))

import pytest
from aiohttp.test_utils import TestClient, TestServer

from cn_social_agent.api.app import create_app
from cn_social_agent.tools.reference_library import reference_library


@pytest.fixture
async def client():
    shutil.rmtree(os.environ["LIBRARY_DATA_DIR"], ignore_errors=True)
    os.makedirs(os.environ["LIBRARY_DATA_DIR"], exist_ok=True)
    reference_library._items.clear()
    reference_library._loaded.clear()
    app = create_app()
    tc = TestClient(TestServer(app))
    await tc.start_server()
    try:
        yield tc
    finally:
        await tc.close()
    reference_library._items.clear()
    reference_library._loaded.clear()


async def _auth_header(tc: TestClient, email: str) -> dict:
    resp = await tc.post("/api/auth/login", json={"email": email, "password": "pw"})
    assert resp.status == 200, await resp.text()
    data = await resp.json()
    token = data["accessToken"]
    return {"Authorization": f"Bearer {token}"}, data["user"]["id"]


async def test_library_upload_list_read_delete(client: TestClient) -> None:
    headers, uid_a = await _auth_header(client, "lib-a@nexus.test")

    # 上传
    resp = await client.post(
        "/api/library",
        headers=headers,
        json={"name": "brand-notes.md", "content": "# 品牌\n语气要克制，突出浏览器直用。"},
    )
    assert resp.status == 201, await resp.text()
    item = await resp.json()
    assert item["name"] == "brand-notes.md"
    assert item["kind"] == "md"

    # 列表（无 content 泄漏）
    resp = await client.get("/api/library", headers=headers)
    items = (await resp.json())["items"]
    assert len(items) == 1
    assert "content" not in items[0]

    # 读取（by id）
    resp = await client.get(f"/api/library/{item['id']}", headers=headers)
    body = await resp.json()
    assert "浏览器直用" in body["item"]["content"]

    # 删除
    resp = await client.delete(f"/api/library/{item['id']}", headers=headers)
    assert resp.status == 200
    resp = await client.get("/api/library", headers=headers)
    assert (await resp.json())["items"] == []


async def test_library_rls_isolation(client: TestClient) -> None:
    """A 上传的资料，B 看不到也读不到。"""
    (ha, _ua) = await _auth_header(client, "lib-a@nexus.test")
    (hb, _ub) = await _auth_header(client, "lib-b@nexus.test")

    resp = await client.post(
        "/api/library", headers=ha,
        json={"name": "secret.csv", "content": "kpi,100"},
    )
    item = await resp.json()

    resp = await client.get("/api/library", headers=hb)
    assert (await resp.json())["items"] == []

    resp = await client.get(f"/api/library/{item['id']}", headers=hb)
    assert resp.status == 404

    resp = await client.delete(f"/api/library/{item['id']}", headers=hb)
    assert resp.status == 404


async def test_library_validation(client: TestClient) -> None:
    (headers, _uc) = await _auth_header(client, "lib-c@nexus.test")

    # 非文本扩展名
    resp = await client.post("/api/library", headers=headers, json={"name": "x.exe", "content": "MZ"})
    assert resp.status == 400

    # 空内容
    resp = await client.post("/api/library", headers=headers, json={"name": "a.md", "content": "  "})
    assert resp.status == 400

    # 重名
    await client.post("/api/library", headers=headers, json={"name": "a.md", "content": "one"})
    resp = await client.post("/api/library", headers=headers, json={"name": "a.md", "content": "two"})
    assert resp.status == 400


async def test_agent_tools_see_library(client: TestClient) -> None:
    """library_list / library_read 工具走同一存储，且按当前租户隔离。"""
    from cn_social_agent.tools.registry import ToolRegistry
    from cn_social_agent.tools.builtin import register_builtin_tools
    from cn_social_agent.tools.context import reset_tool_context, set_tool_context

    (headers, uid) = await _auth_header(client, "lib-a@nexus.test")
    resp = await client.post(
        "/api/library", headers=headers,
        json={"name": "tone-guide.md", "content": "口播语气：生活化，不要 AI 腔。"},
    )
    assert resp.status == 201

    reg = ToolRegistry()
    register_builtin_tools(reg)
    assert reg.get("library_list") is not None
    assert reg.get("library_read") is not None

    token = set_tool_context(user_id=uid)
    try:
        out = await reg.execute("library_list", {})
        assert out.success and out.data["count"] == 1

        out = await reg.execute("library_read", {"query": "语气"})
        assert out.success and out.data["found"]
        assert "不要 AI 腔" in out.data["content"]

        # 其他用户读不到
        set_tool_context(user_id="someone-else")
        out = await reg.execute("library_read", {"query": "语气"})
        assert out.success and not out.data["found"]
    finally:
        reset_tool_context(token)
