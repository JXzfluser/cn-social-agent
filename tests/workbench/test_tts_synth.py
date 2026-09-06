"""TTS synthesize_tts: error shaping, empty-file cleanup, API preference."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cn_social_agent.video.pipeline import _run, synthesize_tts


@pytest.mark.asyncio
async def test_run_puts_stderr_before_argv_noise():
    class FakeProc:
        returncode = 1

        async def communicate(self):
            return b"", b"NoAudioReceived: no audio in response\n"

    with patch(
        "cn_social_agent.video.pipeline.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=FakeProc()),
    ):
        with pytest.raises(RuntimeError, match=r"NoAudioReceived") as ei:
            await _run(
                [
                    "/opt/homebrew/bin/edge-tts",
                    "--voice",
                    "zh-CN-YunxiNeural",
                    "--text",
                    "很长一段旁白会被截断所以以前看不到真正的错误",
                    "--write-media",
                    "/tmp/x.mp3",
                ]
            )
    assert "很长一段旁白" not in str(ei.value)
    assert "cmd failed" not in str(ei.value)


@pytest.mark.asyncio
async def test_synthesize_tts_prefers_api_and_cleans_empty(tmp_path):
    out = tmp_path / "scene_5.mp3"
    out.write_bytes(b"")  # leftover from a prior failed attempt

    async def fake_save(path: str):
        Path(path).write_bytes(b"ID3fake")

    fake_communicate = MagicMock()
    fake_communicate.save = AsyncMock(side_effect=fake_save)
    fake_mod = MagicMock()
    fake_mod.Communicate = MagicMock(return_value=fake_communicate)

    with (
        patch.dict("sys.modules", {"edge_tts": fake_mod}),
            patch("cn_social_agent.video.pipeline.audio_duration", return_value=1.5),
        patch("cn_social_agent.video.pipeline.shutil.which", return_value="/opt/homebrew/bin/edge-tts"),
        patch("cn_social_agent.video.pipeline._run", new=AsyncMock()) as run_mock,
    ):
        # Force import path: synthesize_tts does `import edge_tts` inside.
        # sys.modules patch is enough for that.
        dur = await synthesize_tts("短旁白测试。", out, voice="zh-CN-YunxiNeural")

    assert dur == 1.5
    assert out.is_file() and out.stat().st_size > 0
    run_mock.assert_not_called()
    fake_mod.Communicate.assert_called_once()


@pytest.mark.asyncio
async def test_synthesize_tts_network_error_message(tmp_path):
    out = tmp_path / "bad.mp3"

    async def boom(_path: str):
        raise RuntimeError("Cannot connect to host speech.platform.bing.com")

    fake_communicate = MagicMock()
    fake_communicate.save = AsyncMock(side_effect=boom)
    fake_mod = MagicMock()
    fake_mod.Communicate = MagicMock(return_value=fake_communicate)

    with (
        patch.dict("sys.modules", {"edge_tts": fake_mod}),
        patch("cn_social_agent.video.pipeline.shutil.which", return_value=None),
        patch("cn_social_agent.video.pipeline.asyncio.sleep", new=AsyncMock()),
    ):
        with pytest.raises(RuntimeError, match=r"连不上 Microsoft TTS"):
            await synthesize_tts("旁白", out)

    assert not out.exists() or out.stat().st_size == 0
