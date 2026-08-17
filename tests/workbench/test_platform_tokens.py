"""Token storage tests — InsForge primary, local fallback."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_token_roundtrip(tmp_path, monkeypatch):
    import cn_social_agent.platforms.tokens as tok

    monkeypatch.setattr(tok, "oauth_dir", lambda: tmp_path)
    tok.set_secrets_backend(None)
    await tok.save_token("weixin", "e_demo", {"access_token": "a", "account": "acc"})
    data = await tok.load_token("weixin", "e_demo")
    assert data["access_token"] == "a"
    await tok.clear_token("weixin", "e_demo")
    assert await tok.load_token("weixin", "e_demo") is None


@pytest.mark.asyncio
async def test_platform_config_roundtrip(tmp_path, monkeypatch):
    import cn_social_agent.platforms.tokens as tok

    monkeypatch.setattr(tok, "oauth_dir", lambda: tmp_path)
    tok.set_secrets_backend(None)
    await tok.save_platform_config("weixin", {"app_id": "id1", "app_secret": "sec"})
    cfg = await tok.load_platform_config("weixin")
    assert cfg["app_id"] == "id1"


class _FakeSecrets:
    def __init__(self):
        self.data: dict[str, str] = {}

    async def get_secret(self, key: str):
        return self.data.get(key)

    async def create_secret(self, key: str, value: str):
        self.data[key] = value
        return {"key": key}

    async def update_secret(self, key: str, value: str):
        if key not in self.data:
            return None
        self.data[key] = value
        return {"key": key}

    async def delete_secret(self, key: str):
        self.data.pop(key, None)


@pytest.mark.asyncio
async def test_token_prefers_insforge(tmp_path, monkeypatch):
    import cn_social_agent.platforms.tokens as tok

    monkeypatch.setattr(tok, "oauth_dir", lambda: tmp_path)
    fake = _FakeSecrets()
    tok.set_secrets_backend(fake)
    await tok.save_token("weixin", "owner1", {"access_token": "from_if"})
    # Corrupt local file — InsForge should still win
    path = tok.token_path("weixin", "owner1")
    path.write_text('{"access_token":"local"}', encoding="utf-8")
    data = await tok.load_token("weixin", "owner1")
    assert data["access_token"] == "from_if"
    assert any(k.startswith("CARD_OAUTH_") for k in fake.data)
    tok.set_secrets_backend(None)
