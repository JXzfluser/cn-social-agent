"""End-to-end HTTP smoke test for the Nexus expert workbench.

Boots the real aiohttp application in **memory auth** mode, which makes
``AppState`` wire the RLS-emulating in-memory InsForge backend. The full
request path is therefore exercised: auth → tenant binding → :class:`TaskEngine`
→ :class:`TenantDB` → review → "approved means done", plus per-user isolation
and the i18n dictionary.

Run with::

    PYTHONPATH=src .venv/bin/python -m pytest tests/nexus/test_e2e_routes.py -q
"""

from __future__ import annotations

import os

# Force memory auth so the workbench is fully runnable without a live InsForge,
# and routes use the RLS-emulating memory backend (still isolated per user).
os.environ.setdefault("WORKBENCH_AUTH", "memory")
os.environ.setdefault("WORKBENCH_STORE", "memory")

import pytest

from aiohttp.test_utils import TestClient, TestServer

from cn_social_agent.api.app import create_app


@pytest.fixture
async def client():
    app = create_app()
    tc = TestClient(TestServer(app))
    await tc.start_server()
    try:
        yield tc
    finally:
        await tc.close()


async def _login(tc: TestClient, email: str, password: str) -> dict:
    resp = await tc.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status == 200, await resp.text()
    return await resp.json()


async def _auth_header(tc: TestClient, email: str, password: str) -> dict:
    data = await _login(tc, email, password)
    token = data["accessToken"]
    return {"Authorization": f"Bearer {token}"}


async def test_task_followup_message(client: TestClient) -> None:
    """WorkBuddy-style task conversation: user appends messages to a live task."""
    headers = await _auth_header(client, "frank@nexus.test", "pw-frank")
    created = await client.post(
        "/api/nexus/tasks",
        headers=headers,
        json={"expert_id": "copywriter", "title": "追问测试", "brief": "x", "locale": "zh-CN"},
    )
    task_id = (await created.json())["task"]["id"]

    resp = await client.post(
        f"/api/nexus/tasks/{task_id}/messages",
        headers=headers,
        json={"content": "请补充一版英文标题"},
    )
    assert resp.status == 200, await resp.text()

    detail = await client.get(f"/api/nexus/tasks/{task_id}", headers=headers)
    steps = (await detail.json())["task"]["steps"]
    assert any(s["kind"] == "user" and "英文标题" in s["message"] for s in steps)

    # empty message rejected
    bad = await client.post(
        f"/api/nexus/tasks/{task_id}/messages", headers=headers, json={"content": "  "}
    )
    assert bad.status == 400


async def test_skills_and_agent_tools(client: TestClient) -> None:
    headers = await _auth_header(client, "grace@nexus.test", "pw-grace")
    resp = await client.get("/api/skills", headers=headers)
    assert resp.status == 200
    skills = (await resp.json())["skills"]

    if skills:  # toggle the first skill and confirm the patch sticks
        sid = skills[0]["id"]
        target = not bool(skills[0].get("enabled"))
        p = await client.patch(
            f"/api/skills/{sid}", headers=headers, json={"enabled": target}
        )
        assert p.status == 200, await p.text()
        again = await client.get("/api/skills", headers=headers)
        row = next(s for s in (await again.json())["skills"] if s["id"] == sid)
        assert bool(row["enabled"]) == target

    tools = await client.get("/api/tools", headers=headers)
    assert tools.status == 200


async def test_custom_connectors_crud(client: TestClient) -> None:
    headers = await _auth_header(client, "heidi@nexus.test", "pw-heidi")

    lst = await client.get("/api/connectors", headers=headers)
    assert lst.status == 200
    before = (await lst.json())["connectors"]
    assert before, "catalog should not be empty"

    created = await client.post(
        "/api/connectors/custom",
        headers=headers,
        json={"label": "内部 Wiki", "direction": "ingest", "description": "公司知识库"},
    )
    assert created.status == 201, await created.text()
    cid = (await created.json())["connector"]["id"]

    lst2 = await client.get("/api/connectors", headers=headers)
    rows = (await lst2.json())["connectors"]
    mine = next(r for r in rows if r["id"] == cid)
    assert mine["custom"] is True and mine["label"] == "内部 Wiki"

    # toggle custom connector via generic patch
    p = await client.patch(
        "/api/connectors", headers=headers, json={"id": cid, "enabled": False}
    )
    assert p.status == 200
    rows2 = (await (await client.get("/api/connectors", headers=headers)).json())["connectors"]
    assert next(r for r in rows2 if r["id"] == cid)["enabled"] is False

    # isolation: another user must not see it
    h_other = await _auth_header(client, "ivy@nexus.test", "pw-ivy")
    rows3 = (await (await client.get("/api/connectors", headers=h_other)).json())["connectors"]
    assert not any(r["id"] == cid for r in rows3)

    # delete
    d = await client.delete(f"/api/connectors/custom/{cid}", headers=headers)
    assert d.status == 200
    gone = await client.delete(f"/api/connectors/custom/{cid}", headers=headers)
    assert gone.status == 404


async def test_cards_categories_and_history(client: TestClient) -> None:
    headers = await _auth_header(client, "karl@nexus.test", "pw-karl")
    cats = await client.get("/api/cards/categories", headers=headers)
    assert cats.status == 200
    hist = await client.get("/api/cards/history", headers=headers)
    assert hist.status == 200


async def test_task_rename(client: TestClient) -> None:
    headers = await _auth_header(client, "lena@nexus.test", "pw-lena")
    created = await client.post(
        "/api/nexus/tasks",
        headers=headers,
        json={"expert_id": "copywriter", "title": "旧标题", "brief": "x", "locale": "zh-CN"},
    )
    task_id = (await created.json())["task"]["id"]

    r = await client.patch(
        f"/api/nexus/tasks/{task_id}", headers=headers, json={"title": "新标题"}
    )
    assert r.status == 200, await r.text()
    detail = await client.get(f"/api/nexus/tasks/{task_id}", headers=headers)
    assert (await detail.json())["task"]["title"] == "新标题"

    # empty title rejected
    bad = await client.patch(f"/api/nexus/tasks/{task_id}", headers=headers, json={"title": " "})
    assert bad.status == 400

    # isolation: another user cannot rename it
    h_other = await _auth_header(client, "mike@nexus.test", "pw-mike")
    forbidden = await client.patch(
        f"/api/nexus/tasks/{task_id}", headers=h_other, json={"title": "hack"}
    )
    assert forbidden.status in (403, 404)


async def test_register_and_isolated_account(client: TestClient) -> None:
    """Register flow mints a token and the new account starts empty."""
    import random
    email = f"reg{random.randint(1000, 99999)}@nexus.test"
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "pw-reg-123", "name": "注册用户"},
    )
    assert resp.status == 200, await resp.text()
    data = await resp.json()
    token = data.get("accessToken") or data.get("token")
    assert token, "register should return a token"

    headers = {"Authorization": f"Bearer {token}"}
    tasks = await client.get("/api/nexus/tasks", headers=headers)
    assert tasks.status == 200
    assert (await tasks.json())["tasks"] == []

    prof = await client.put(
        "/api/nexus/profile", headers=headers, json={"display_name": "注册用户"}
    )
    assert prof.status == 200


async def test_llm_settings_and_automations(client: TestClient) -> None:
    """OpenWorkBuddy-parity surfaces: model hot-switch + automations."""
    headers = await _auth_header(client, "nina@nexus.test", "pw-nina")

    cur = await client.get("/api/settings/llm", headers=headers)
    assert cur.status == 200, await cur.text()
    body = await cur.json()
    assert body["mode"] and isinstance(body["providers"], list)

    mock = next((p for p in body["providers"] if p["id"] == "mock"), None)
    if mock:  # switch to mock and back — hot-switch contract
        r = await client.post(
            "/api/settings/llm", headers=headers, json={"mode": "mock", "model": ""}
        )
        assert r.status == 200
        assert (await r.json())["mode"] == "mock"

    autos = await client.get("/api/automations", headers=headers)
    assert autos.status == 200
    assert "recipes" in (await autos.json())


async def test_nexus_frontend_served(client: TestClient) -> None:
    # /nexus and /nexus/ must both serve the SPA (index registered before static).
    for path in ("/nexus", "/nexus/"):
        resp = await client.get(path)
        assert resp.status == 200, path
        body = await resp.text()
        assert "app.js" in body
    js = await client.get("/nexus/app.js")
    assert js.status == 200
    css = await client.get("/nexus/styles.css")
    assert css.status == 200


async def test_health_and_experts(client: TestClient) -> None:
    headers = await _auth_header(client, "alice@nexus.test", "pw-alice")
    h = await client.get("/api/nexus/health", headers=headers)
    assert h.status == 200
    body = await h.json()
    assert body["ok"] is True
    assert body["user"]
    assert body["isolation"] == "rls"

    e = await client.get("/api/nexus/experts", headers=headers)
    assert e.status == 200
    experts = (await e.json())["experts"]
    assert len(experts) >= 1
    # Expert exposes its acceptance rubric (the heart of "tasks can be accepted").
    assert any(x.get("blockers") for x in experts)


async def test_full_task_lifecycle_approved(client: TestClient) -> None:
    headers = await _auth_header(client, "bob@nexus.test", "pw-bob")

    # Create
    c = await client.post(
        "/api/nexus/tasks",
        headers=headers,
        json={
            "expert_id": "copywriter",
            "title": "SaaS 落地页文案",
            "brief": "为一款 AI 笔记工具写首屏文案，突出本地优先与隐私。",
            "locale": "zh-CN",
        },
    )
    assert c.status == 201, await c.text()
    task = (await c.json())["task"]
    assert task["status"] == "draft"
    task_id = task["id"]
    assert task_id

    # Run (offline runner falls back; rubric + human gate must still pass)
    r = await client.post(f"/api/nexus/tasks/{task_id}/run", headers=headers)
    assert r.status == 200, await r.text()
    ran = (await r.json())["task"]
    # Offline draft + human sign-off gate ⇒ auto-gates pass, human pending,
    # so the engine leaves it in review rather than auto-approving.
    assert ran["status"] in ("submitted", "reviewing", "approved")
    assert ran.get("review") is not None

    # Human approval is what makes it "done".
    d = await client.post(
        f"/api/nexus/tasks/{task_id}/decide",
        headers=headers,
        json={"decision": "approve", "note": "looks good"},
    )
    assert d.status == 200, await d.text()
    decided = (await d.json())["task"]
    assert decided["status"] == "approved", decided
    assert decided["is_done"] is True

    # Detail returns artifacts produced by the runner.
    g = await client.get(f"/api/nexus/tasks/{task_id}", headers=headers)
    assert g.status == 200
    detail = (await g.json())["task"]
    assert detail["artifacts"]


async def test_locale_switch_and_i18n(client: TestClient) -> None:
    headers = await _auth_header(client, "carol@nexus.test", "pw-carol")

    i18n = await client.get("/api/i18n/en-US", headers=headers)
    assert i18n.status == 200
    msgs = (await i18n.json())["messages"]
    assert msgs["app.name"] == "Expert Workbench"

    prof = await client.put("/api/nexus/profile", headers=headers, json={"locale": "en-US"})
    assert prof.status == 200
    assert (await prof.json())["profile"]["locale"] == "en-US"


async def test_per_user_isolation(client: TestClient) -> None:
    h_a = await _auth_header(client, "dave@nexus.test", "pw-dave")
    h_b = await _auth_header(client, "erin@nexus.test", "pw-erin")

    created = await client.post(
        "/api/nexus/tasks",
        headers=h_a,
        json={"expert_id": "copywriter", "title": "D 的私密任务", "brief": "x", "locale": "zh-CN"},
    )
    assert created.status == 201
    task_id = (await created.json())["task"]["id"]

    # B sees no tasks at all.
    lst = await client.get("/api/nexus/tasks", headers=h_b)
    assert lst.status == 200
    assert (await lst.json())["tasks"] == []

    # B cannot read A's task (RLS in the memory backend answers 404).
    blocked = await client.get(f"/api/nexus/tasks/{task_id}", headers=h_b)
    assert blocked.status in (403, 404)

    # A can still read their own.
    ok = await client.get(f"/api/nexus/tasks/{task_id}", headers=h_a)
    assert ok.status == 200
