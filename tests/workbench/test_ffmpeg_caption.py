"""ffmpeg error surfacing + drawtext-less caption fallback."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cn_social_agent.video.pipeline import (
    _stderr_gist,
    ffmpeg_has_filter,
    mux_video_audio,
    write_caption_overlay,
)

FFMPEG_BANNER = """ffmpeg version 8.1 Copyright (c) 2000-2026 the FFmpeg developers
  built with Apple clang version 21.0.0
  configuration: --prefix=/opt/homebrew/Cellar/ffmpeg/8.1 --enable-shared
  libavutil      60. 26.100 / 60. 26.100
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'scene_1_agnes.mp4':
  Duration: 00:00:05.04, start: 0.000000, bitrate: 2735 kb/s
[AVFilterGraph @ 0x954c14580] No such filter: 'drawtext'
Error opening output file /tmp/out.mp4.
Error opening output files: Filter not found
"""


def test_stderr_gist_keeps_tail_not_banner():
    gist = _stderr_gist(FFMPEG_BANNER)
    assert "No such filter: 'drawtext'" in gist
    assert "ffmpeg version" not in gist
    assert "configuration:" not in gist


def test_stderr_gist_handles_empty():
    assert _stderr_gist("") == "no stderr"
    assert _stderr_gist("   \n\n") == "no stderr"


def test_ffmpeg_has_filter_parses_listing():
    listing = " T.. drawtext           V->V       Draw text on top of video frames.\n"
    ffmpeg_has_filter.cache_clear()
    with patch(
        "cn_social_agent.video.pipeline.subprocess.run",
        return_value=type("R", (), {"stdout": listing})(),
    ):
        assert ffmpeg_has_filter("drawtext") is True
        ffmpeg_has_filter.cache_clear()
        assert ffmpeg_has_filter("nonexistent") is False
    ffmpeg_has_filter.cache_clear()


def test_write_caption_overlay_is_transparent_png(tmp_path):
    from PIL import Image

    out = write_caption_overlay(tmp_path / "cap.png", "深采成刊", width=200, height=400)
    img = Image.open(out)
    assert img.mode == "RGBA"
    assert img.size == (200, 400)
    assert img.getpixel((0, 0))[3] == 0  # corner stays transparent


@pytest.mark.asyncio
async def test_mux_uses_overlay_when_drawtext_missing(tmp_path):
    video, audio, out = tmp_path / "a.mp4", tmp_path / "a.mp3", tmp_path / "o.mp4"
    for p in (video, audio):
        p.write_bytes(b"x")

    with (
        patch("cn_social_agent.video.pipeline.ffmpeg_has_filter", return_value=False),
        patch("cn_social_agent.video.pipeline._cjk_fontfile", return_value="/f.ttc"),
        patch("cn_social_agent.video.pipeline._run", new=AsyncMock()) as run_mock,
    ):
        await mux_video_audio(video, audio, out, 5.0, overlay_text="标题文字")

    cmd = run_mock.call_args[0][0]
    assert "drawtext" not in " ".join(cmd)
    assert "-filter_complex" in cmd
    assert "overlay=0:0:format=auto" in " ".join(cmd)
    assert (tmp_path / "o_caption.png").is_file()


@pytest.mark.asyncio
async def test_mux_uses_drawtext_when_available(tmp_path):
    video, audio, out = tmp_path / "a.mp4", tmp_path / "a.mp3", tmp_path / "o.mp4"
    for p in (video, audio):
        p.write_bytes(b"x")

    with (
        patch("cn_social_agent.video.pipeline.ffmpeg_has_filter", return_value=True),
        patch("cn_social_agent.video.pipeline._cjk_fontfile", return_value="/f.ttc"),
        patch("cn_social_agent.video.pipeline._run", new=AsyncMock()) as run_mock,
    ):
        await mux_video_audio(video, audio, out, 5.0, overlay_text="标题文字")

    joined = " ".join(run_mock.call_args[0][0])
    assert "drawtext" in joined
    assert "-filter_complex" not in joined
    assert not (tmp_path / "o_caption.png").exists()


@pytest.mark.asyncio
async def test_mux_without_caption_skips_both(tmp_path):
    video, audio, out = tmp_path / "a.mp4", tmp_path / "a.mp3", tmp_path / "o.mp4"
    for p in (video, audio):
        p.write_bytes(b"x")

    with (
        patch("cn_social_agent.video.pipeline.ffmpeg_has_filter", return_value=False),
        patch("cn_social_agent.video.pipeline._run", new=AsyncMock()) as run_mock,
    ):
        await mux_video_audio(video, audio, out, 5.0, overlay_text="")

    joined = " ".join(run_mock.call_args[0][0])
    assert "drawtext" not in joined
    assert "overlay" not in joined
    assert not Path(tmp_path / "o_caption.png").exists()
