import pytest

from cn_social_agent.tools.hotspot_handoff import build_handoff_payload


@pytest.mark.asyncio
async def test_handoff_koubo_shape():
    out = await build_handoff_payload(
        title="Test Topic",
        url="https://example.com/post",
        source="hn",
        why="社区热议",
        topic_key="test-topic",
        track="koubo",
        research_notes="已有笔记",
    )
    assert out["ok"] is True
    assert out["track"] == "koubo"
    assert out["propose_short_video"] is True
    assert out["video_track"] == "koubo"
    assert out["topic"] == "Test Topic"
    assert out["topic_key"] == "test-topic"
    assert "社区热议" in out["research_notes"]
    assert "https://example.com/post" in out["research_notes"]
    assert "已有笔记" in out["research_notes"]


@pytest.mark.asyncio
async def test_handoff_presentation_shape():
    out = await build_handoff_payload(
        title="LLM Agent 框架",
        url="https://example.com/agent",
        source="github",
        why="近创高星",
        track="presentation",
        research_notes="README 摘要",
    )
    assert out["ok"] is True
    assert out["track"] == "presentation"
    assert out["propose_presentation"] is True
    assert out["auto_draft"] is True
    assert out["needs_deep_draft"] is True
    assert out["aspect"] == "9:16"
    assert out["theme"] == "talent-map"
    assert "README 摘要" in out["research_notes"]


@pytest.mark.asyncio
async def test_handoff_journal_shape():
    out = await build_handoff_payload(
        title="少数派 AI 工具盘点",
        url="https://sspai.com/x",
        source="sspai",
        why="中文讨论热",
        track="journal",
        research_notes="正文摘要",
    )
    assert out["ok"] is True
    assert out["track"] == "journal"
    assert out["propose_cards"] is True
    assert out["roles"] == ["少数派 AI 工具盘点"]
    assert out["category"] == "product_explain"
    assert "正文摘要" in out["research_notes"]


@pytest.mark.asyncio
async def test_handoff_rejects_bad_track():
    out = await build_handoff_payload(title="Foo", track="podcast", research_notes="x")
    assert out["ok"] is False
    assert "track" in out["error"]


@pytest.mark.asyncio
async def test_handoff_requires_title():
    out = await build_handoff_payload(title="   ", track="koubo", research_notes="x")
    assert out["ok"] is False
    assert "title" in out["error"]


@pytest.mark.asyncio
async def test_handoff_skips_fetch_when_notes_given(monkeypatch):
    async def boom(*args, **kwargs):
        raise AssertionError("should not fetch when research_notes provided")

    monkeypatch.setattr("cn_social_agent.tools.builtin.tool_fetch_url_text", boom)
    out = await build_handoff_payload(
        title="No Network",
        url="https://example.com",
        track="koubo",
        research_notes="离线笔记",
    )
    assert out["ok"] is True
    assert "离线笔记" in out["research_notes"]


@pytest.mark.asyncio
async def test_handoff_fetches_when_notes_empty(monkeypatch):
    async def fake_fetch(url, max_chars=8000):
        return {"ok": True, "url": url, "title": "文章标题", "text": "正文" * 3000}

    monkeypatch.setattr("cn_social_agent.tools.builtin.tool_fetch_url_text", fake_fetch)
    out = await build_handoff_payload(
        title="Fetch Me",
        url="https://example.com/a",
        source="hn",
        why="社区热议",
        track="koubo",
    )
    assert out["ok"] is True
    assert "文章标题" in out["research_notes"]
    assert len(out["research_notes"]) < 2300


@pytest.mark.asyncio
async def test_handoff_survives_fetch_failure(monkeypatch):
    async def fake_fetch(url, max_chars=8000):
        return {"ok": False, "error": "HTTP 404", "text": ""}

    monkeypatch.setattr("cn_social_agent.tools.builtin.tool_fetch_url_text", fake_fetch)
    out = await build_handoff_payload(
        title="Broken",
        url="https://example.com/404",
        track="journal",
    )
    assert out["ok"] is True
    assert "抓取失败" in out["research_notes"]
