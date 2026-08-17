"""Tests for card platform publish (P0 + adapters)."""

from __future__ import annotations

import pytest


def test_get_publisher_mock():
    from cn_social_agent.platforms import get_publisher, list_platforms

    p = get_publisher("mock")
    assert p is not None
    assert "mock" in list_platforms()
    assert "weixin" in list_platforms()
    assert "toutiao" in list_platforms()
    assert "xiaohongshu" in list_platforms()


@pytest.mark.asyncio
async def test_mock_publish_draft(tmp_path):
    from cn_social_agent.platforms import get_publisher

    img = tmp_path / "c.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    pub = get_publisher("mock")
    r = await pub.publish(
        user_id="u1",
        title="A · B",
        image_paths=[img],
        direct=False,
        meta={},
    )
    assert r["platform"] == "mock"
    assert r["status"] == "draft"
    assert r["external_id"]


def test_resolve_publish_title_from_tags():
    from cn_social_agent.cards.publish.title import resolve_publish_title

    assert resolve_publish_title({"tags": ["Agent", "RAG"], "title": "X"}) == "Agent · RAG"


def test_resolve_publish_title_fallback_and_clip():
    from cn_social_agent.cards.publish.title import resolve_publish_title

    assert resolve_publish_title({"tags": [], "title": "仅标题"}) == "仅标题"
    long_tags = ["很长标签名"] * 20
    t = resolve_publish_title({"tags": long_tags, "title": "X"}, max_len=20)
    assert len(t) <= 20


@pytest.mark.asyncio
async def test_publish_card_with_mock(tmp_path, monkeypatch):
    import cn_social_agent.cards.history as hist
    import cn_social_agent.cards.publish.images as imgs

    monkeypatch.setattr(hist, "history_dir", lambda: tmp_path)
    monkeypatch.setattr(imgs, "exports_dir", lambda: tmp_path / "exports")
    from cn_social_agent.cards.history import save_history_record
    from cn_social_agent.cards.publish.service import publish_card

    rec = save_history_record(
        {
            "cover": {"title": "T", "tags": ["A", "B"]},
            "knowledge": [{"topicTitle": "k1"}],
            "mode": "ai",
        },
        email="demo@local.test",
        user_id="u_demo_local",
    )
    exp = tmp_path / "exports" / rec["id"]
    exp.mkdir(parents=True)
    (exp / "00_cover.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (exp / "01_k0.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    out = await publish_card(
        history_id=rec["id"],
        platforms=["mock"],
        direct=False,
        title_override="",
        user_id="u_demo_local",
        email="demo@local.test",
    )
    assert out["results"][0]["status"] == "draft"
    assert out["title"] == "A · B"


@pytest.mark.asyncio
async def test_cards_publish_requires_auth(monkeypatch):
    from aiohttp.test_utils import TestClient, TestServer

    from cn_social_agent.api import create_app

    monkeypatch.setenv("WORKBENCH_STORE", "memory")
    monkeypatch.setenv("WORKBENCH_LLM", "mock")
    monkeypatch.setenv("INSFORGE_ENABLED", "false")
    app = create_app()
    async with TestClient(TestServer(app)) as client:
        r = await client.post(
            "/api/cards/publish",
            json={"history_id": "x", "platforms": ["mock"]},
        )
        assert r.status == 401


@pytest.mark.asyncio
async def test_cards_publish_mock_ok(tmp_path, monkeypatch):
    import cn_social_agent.cards.history as hist
    import cn_social_agent.cards.publish.images as imgs
    from aiohttp.test_utils import TestClient, TestServer

    from cn_social_agent.api import create_app
    from cn_social_agent.cards.history import save_history_record

    monkeypatch.setenv("WORKBENCH_STORE", "memory")
    monkeypatch.setenv("WORKBENCH_LLM", "mock")
    monkeypatch.setenv("INSFORGE_ENABLED", "false")
    monkeypatch.setenv("CARD_PUBLISH_ALLOW_MOCK", "1")
    hist_dir = tmp_path / "hist"
    hist_dir.mkdir(parents=True)
    monkeypatch.setattr(hist, "history_dir", lambda: hist_dir)
    monkeypatch.setattr(imgs, "exports_dir", lambda: tmp_path / "exports")

    rec = save_history_record(
        {
            "cover": {"title": "T", "tags": ["X", "Y"]},
            "knowledge": [{"topicTitle": "k1"}],
            "mode": "ai",
        },
        email="demo@local.test",
        user_id="u_demo_local",
    )
    exp = tmp_path / "exports" / rec["id"]
    exp.mkdir(parents=True)
    (exp / "00.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    app = create_app()
    async with TestClient(TestServer(app)) as client:
        login = await client.post(
            "/api/auth/login",
            json={"email": "demo@local.test", "password": "demo123456"},
        )
        assert login.status == 200
        body = await login.json()
        token = body.get("accessToken") or body.get("access_token")
        assert token
        r = await client.post(
            "/api/cards/publish",
            json={"history_id": rec["id"], "platforms": ["mock"], "direct": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status == 200, await r.text()
        data = await r.json()
        assert data["results"][0]["platform"] == "mock"
        assert data["title"] == "X · Y"


@pytest.mark.asyncio
async def test_weixin_status_not_configured(tmp_path, monkeypatch):
    monkeypatch.delenv("WEIXIN_APP_ID", raising=False)
    monkeypatch.delenv("WEIXIN_APP_SECRET", raising=False)
    import cn_social_agent.platforms.tokens as tok
    import cn_social_agent.platforms.weixin.publisher as wxpub

    monkeypatch.setattr(tok, "oauth_dir", lambda: tmp_path)
    tok.set_secrets_backend(None)

    async def _empty(_p):
        return {}

    monkeypatch.setattr(tok, "load_platform_config", _empty)
    monkeypatch.setattr(wxpub, "load_platform_config", _empty)
    st = await wxpub.WeixinPublisher().status(user_id="u")
    assert st["ready"] is False


@pytest.mark.asyncio
async def test_toutiao_publish_skipped(monkeypatch):
    from cn_social_agent.platforms.toutiao.publisher import ToutiaoPublisher

    r = await ToutiaoPublisher().publish(
        user_id="u",
        title="t",
        image_paths=[],
        direct=False,
        meta={},
    )
    assert r["status"] == "skipped"
