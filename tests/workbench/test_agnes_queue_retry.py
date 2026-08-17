"""Agnes create_video retries while the render queue is saturated."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from cn_social_agent.api.video_routes import _exc_text
from cn_social_agent.video.agnes_client import AgnesVideoClient, is_queue_full

QUEUE_FULL_BODY = (
    '{"code":"video_queue_full","message":"video queue is full, please retry later"}'
)


class FakeResp:
    def __init__(self, status_code: int, text: str = "", payload=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload or {}

    @property
    def is_error(self) -> bool:
        return self.status_code >= 400

    def json(self):
        return self._payload


def _client_ctx(responses):
    """Patch httpx.AsyncClient so POST returns queued responses in order."""
    post = AsyncMock(side_effect=responses)
    fake = AsyncMock()
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.__aexit__ = AsyncMock(return_value=False)
    fake.post = post
    return patch("cn_social_agent.video.agnes_client.httpx.AsyncClient", return_value=fake), post


def test_is_queue_full_detection():
    assert is_queue_full(503, QUEUE_FULL_BODY)
    assert is_queue_full(429, "video queue is FULL")
    assert not is_queue_full(503, "gateway timeout")
    assert not is_queue_full(400, QUEUE_FULL_BODY)


@pytest.mark.asyncio
async def test_create_video_retries_then_succeeds(monkeypatch):
    monkeypatch.setenv("AGNES_API_KEY", "k")
    monkeypatch.setenv("AGNES_QUEUE_BACKOFF_SECONDS", "1")
    ctx, post = _client_ctx(
        [
            FakeResp(503, QUEUE_FULL_BODY),
            FakeResp(503, QUEUE_FULL_BODY),
            FakeResp(200, payload={"video_id": "v1"}),
        ]
    )
    notes: list[str] = []

    async def on_progress(_pct, msg):
        notes.append(msg)

    with ctx, patch("cn_social_agent.video.agnes_client.asyncio.sleep", new=AsyncMock()):
        out = await AgnesVideoClient(api_key="k").create_video("p", on_progress=on_progress)

    assert out == {"video_id": "v1"}
    assert post.await_count == 3
    assert any("队列已满" in n for n in notes)


@pytest.mark.asyncio
async def test_create_video_queue_full_exhausted_message(monkeypatch):
    monkeypatch.setenv("AGNES_API_KEY", "k")
    monkeypatch.setenv("AGNES_QUEUE_RETRIES", "3")
    ctx, post = _client_ctx([FakeResp(503, QUEUE_FULL_BODY) for _ in range(3)])

    with ctx, patch("cn_social_agent.video.agnes_client.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(RuntimeError, match=r"Agnes 视频队列持续排满") as ei:
            await AgnesVideoClient(api_key="k").create_video("p")

    assert post.await_count == 3
    assert "L0" in str(ei.value)


@pytest.mark.asyncio
async def test_create_video_does_not_retry_client_error(monkeypatch):
    monkeypatch.setenv("AGNES_API_KEY", "k")
    ctx, post = _client_ctx([FakeResp(400, "bad prompt")])

    with ctx, patch("cn_social_agent.video.agnes_client.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(RuntimeError, match=r"Agnes video create 400"):
            await AgnesVideoClient(api_key="k").create_video("p")

    assert post.await_count == 1


def test_exc_text_maps_queue_full():
    assert "稍后重试" in _exc_text(RuntimeError(f"Agnes video create 503: {QUEUE_FULL_BODY}"))
    exhausted = _exc_text(RuntimeError("Agnes 视频队列持续排满（已重试 6 次）。可先用 L0 本地渲染出片。"))
    assert "队列持续排满" in exhausted
