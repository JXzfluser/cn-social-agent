"""Characterization tests: lock current render_one_scene / mux_video_audio behavior.

Safety net for the pipeline split + quality sprint (design doc 20260822).
These tests assert CURRENT behavior, including known quirks (num_frames=121,
-stream_loop hard looping). Deliberate behavior changes must update these
tests explicitly in the same commit.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

import cn_social_agent.video.pipeline as pipeline


@pytest.fixture()
def video_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "videos"
    root.mkdir()
    monkeypatch.setattr(pipeline, "VIDEO_ROOT", root)
    return root


def _scene(role: str = "value", **extra: object) -> dict:
    sc: dict = {"scene_num": 1, "content": "旁白内容", "role": role}
    sc.update(extra)
    return sc


def _scene_with_role(role: str) -> dict:
    """Scene with image_path JSON containing role (needed for current pipeline to pick up role)."""
    return _scene(role=role, image_path=json.dumps({"role": role, "on_screen": ""}))


class _RunCapture:
    def __init__(self) -> None:
        self.cmds: list[list[str]] = []

    async def __call__(self, cmd: list[str]) -> None:
        self.cmds.append(cmd)


class _FakeAgnesClient:
    """Mock that mimics AgnesVideoClient class structure (classmethod + instance)."""
    instances: list["_FakeAgnesClient"] = []

    def __init__(self, **kw: object) -> None:
        self.kw = kw
        _FakeAgnesClient.instances.append(self)

    @classmethod
    def configured(cls) -> bool:
        return True

    async def generate_to_file(self, prompt, out_path, *, width=768, height=1344, num_frames=121, frame_rate=24, **kw):
        self.kw.update({"prompt": prompt, "out": str(out_path), "width": width, "height": height, "num_frames": num_frames, "frame_rate": frame_rate})
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"agnes")


# ---------------------------------------------------------------------------
# mux_video_audio — command shape
# ---------------------------------------------------------------------------

def test_mux_hard_loops_plate(video_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cap = _RunCapture()
    monkeypatch.setattr(pipeline, "_run", cap)
    monkeypatch.setattr(pipeline, "_cjk_fontfile", lambda: "")
    v = video_root / "p.mp4"; a = video_root / "a.mp3"; o = video_root / "o.mp4"
    v.write_bytes(b"v"); a.write_bytes(b"a")
    asyncio.run(pipeline.mux_video_audio(v, a, o, duration=12.0))
    cmd = cap.cmds[0]
    assert cmd[0] == "ffmpeg"
    i = cmd.index("-stream_loop")
    assert cmd[i + 1] == "-1", "5s plate loops to fill 12s narration (current quirk)"
    assert "-shortest" in cmd
    assert cmd[-1] == str(o)


def test_mux_scales_plate_to_1080x1920(video_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cap = _RunCapture()
    monkeypatch.setattr(pipeline, "_run", cap)
    monkeypatch.setattr(pipeline, "_cjk_fontfile", lambda: "")
    v = video_root / "p.mp4"; a = video_root / "a.mp3"; o = video_root / "o.mp4"
    v.write_bytes(b"v"); a.write_bytes(b"a")
    asyncio.run(pipeline.mux_video_audio(v, a, o, duration=3.0))
    vf = cap.cmds[0][cap.cmds[0].index("-vf") + 1]
    assert "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" in vf


def test_mux_duration_floors_at_0_8s(video_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cap = _RunCapture()
    monkeypatch.setattr(pipeline, "_run", cap)
    monkeypatch.setattr(pipeline, "_cjk_fontfile", lambda: "")
    v = video_root / "p.mp4"; a = video_root / "a.mp3"; o = video_root / "o.mp4"
    v.write_bytes(b"v"); a.write_bytes(b"a")
    asyncio.run(pipeline.mux_video_audio(v, a, o, duration=0.0))
    t_idx = cap.cmds[0].index("-t") + 1
    assert cap.cmds[0][t_idx] == "0.800"


def test_mux_drawtext_when_font_and_filter(video_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cap = _RunCapture()
    monkeypatch.setattr(pipeline, "_run", cap)
    fnt = tmp_path / "f.ttf"; fnt.write_bytes(b"f")
    monkeypatch.setattr(pipeline, "_cjk_fontfile", lambda: str(fnt))
    monkeypatch.setattr(pipeline, "ffmpeg_has_filter", lambda n: n == "drawtext")
    v = video_root / "p.mp4"; a = video_root / "a.mp3"; o = video_root / "o.mp4"
    v.write_bytes(b"v"); a.write_bytes(b"a")
    asyncio.run(pipeline.mux_video_audio(v, a, o, duration=3.0, overlay_text="标题文字"))
    vf = cap.cmds[0][cap.cmds[0].index("-vf") + 1]
    assert "drawtext=" in vf
    assert "fontsize=54" in vf


def test_mux_png_plate_fallback(video_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cap = _RunCapture()
    monkeypatch.setattr(pipeline, "_run", cap)
    monkeypatch.setattr(pipeline, "_cjk_fontfile", lambda: "/no.ttf")
    monkeypatch.setattr(pipeline, "ffmpeg_has_filter", lambda n: False)
    v = video_root / "p.mp4"; a = video_root / "a.mp3"; o = video_root / "o.mp4"
    v.write_bytes(b"v"); a.write_bytes(b"a")
    asyncio.run(pipeline.mux_video_audio(v, a, o, duration=3.0, overlay_text="钩子"))
    cmd = cap.cmds[0]
    assert cmd.count("-i") >= 3, "PNG caption plate added as third input"
    assert any("overlay=0:0" in p for p in cmd)


# ---------------------------------------------------------------------------
# render_one_scene — local mode
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_local(monkeypatch: pytest.MonkeyPatch) -> dict:
    calls: dict = {"tts": [], "keys": [], "copy": [], "clip": []}
    async def fake_tts(narration, audio, voice="zh-CN-XiaoxiaoNeural"):
        calls["tts"].append({"narration": narration, "audio": str(audio), "voice": voice})
        return 3.5
    def fake_keys(root, n_keys=6, **kwargs):
        calls["keys"].append({"root": str(root), "n_keys": n_keys})
        return [Path(str(root) + "_k1"), Path(str(root) + "_kN")]
    def fake_copy(src, dst):
        calls["copy"].append({"src": str(src), "dst": str(dst)})
        d = Path(dst); d.parent.mkdir(parents=True, exist_ok=True); d.write_bytes(b"x")
    async def fake_clip(image, audio, clip, dur, motion="", role="", keyframes=None):
        calls["clip"].append({"motion": motion, "role": role, "dur": dur})
        Path(clip).write_bytes(b"x")
    monkeypatch.setattr(pipeline, "synthesize_tts", fake_tts)
    monkeypatch.setattr(pipeline, "write_scene_keyframes", fake_keys)
    monkeypatch.setattr(pipeline.shutil, "copyfile", fake_copy)
    monkeypatch.setattr(pipeline, "render_scene_clip", fake_clip)
    return calls


@pytest.mark.asyncio
async def test_local_render_orchestration(video_root: Path, mock_local: dict) -> None:
    result = await pipeline.render_one_scene(
        project_id="p1", scene=_scene_with_role("hook"), idx=1, total_scenes=18, title="标题"
    )
    root = video_root / "p1"
    assert result["tts_path"] == str(root / "scene_1.mp3")
    assert result["clip_path"] == str(root / "scene_1.mp4")
    assert result["tts_duration_seconds"] == 3.5
    assert result["meta"]["scene_render_mode"] == "local"
    assert mock_local["tts"][0]["narration"] == "旁白内容"
    assert mock_local["keys"][0]["n_keys"] == 8, "round(3.5 * 2.2) = 8"
    assert mock_local["clip"][0]["motion"] == "punch_in", "hook -> punch_in via _ROLE_MOTION"
    assert mock_local["clip"][0]["role"] == "hook"
    packed = json.loads(result["image_path"])
    assert packed.get("poster_path") == str(root / "scene_1.png")


@pytest.mark.asyncio
async def test_local_render_invalid_mode_falls_back_to_local(video_root: Path, mock_local: dict) -> None:
    result = await pipeline.render_one_scene(
        project_id="p1", scene=_scene(), idx=1, total_scenes=1, title="t",
        render_mode="invalid_garbage",
    )
    assert result["meta"]["scene_render_mode"] == "local"


# ---------------------------------------------------------------------------
# render_one_scene — agnes-video mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agnes_render_uses_dynamic_num_frames(
    video_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After refactor: num_frames is dynamic based on TTS duration."""
    _FakeAgnesClient.instances.clear()
    monkeypatch.setattr(pipeline, "_run", lambda c: asyncio.sleep(0))
    monkeypatch.setattr(pipeline, "_cjk_fontfile", lambda: "")
    # Mock TTS to return predictable 5.0s duration
    async def fake_tts(narration, audio, voice="zh-CN-XiaoxiaoNeural"):
        audio.parent.mkdir(parents=True, exist_ok=True)
        audio.write_bytes(b"tts")
        return 5.0
    monkeypatch.setattr(pipeline, "synthesize_tts", fake_tts)
    # Mock resolution probe to return known values
    async def fake_probe():
        return (768, 1344)
    monkeypatch.setattr(pipeline, "probe_agnes_resolution", fake_probe)
    import cn_social_agent.video.agnes_client as ac_mod
    monkeypatch.setattr(ac_mod, "AgnesVideoClient", _FakeAgnesClient)

    result = await pipeline.render_one_scene(
        project_id="p1", scene=_scene_with_role("hook"), idx=1, total_scenes=5,
        title="T", render_mode="agnes-video",
    )

    assert len(_FakeAgnesClient.instances) == 1
    kw = _FakeAgnesClient.instances[0].kw
    # 5.0s * 24fps = 120 -> align to 8n+1 -> 121
    assert kw.get("num_frames") == 121, "5.0s * 24 = 120 -> align to 121"
    assert kw.get("width") == 768
    assert kw.get("height") == 1344
    assert result["meta"]["scene_render_mode"] == "agnes-video"


@pytest.mark.asyncio
async def test_agnes_render_reuses_plate_on_tts_only_refresh(
    video_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CURRENT behavior: tts-only refresh with existing plate skips generate_to_file."""
    _FakeAgnesClient.instances.clear()
    monkeypatch.setattr(pipeline, "_run", lambda c: asyncio.sleep(0))
    monkeypatch.setattr(pipeline, "_cjk_fontfile", lambda: "")
    root = video_root / "p1"
    root.mkdir(parents=True, exist_ok=True)
    (root / "scene_1_agnes.mp4").write_bytes(b"old_plate")
    import cn_social_agent.video.agnes_client as ac_mod
    monkeypatch.setattr(ac_mod, "AgnesVideoClient", _FakeAgnesClient)

    await pipeline.render_one_scene(
        project_id="p1", scene=_scene(), idx=1, total_scenes=1, title="T",
        render_mode="agnes-video", refresh="tts",
    )

    assert len(_FakeAgnesClient.instances) == 1, "AgnesVideoClient always instantiated (line 2749)"
    assert not _FakeAgnesClient.instances[0].kw.get("out"), "generate_to_file NOT called on tts-only refresh with existing plate"


@pytest.mark.asyncio
async def test_agnes_not_configured_raises(video_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import cn_social_agent.video.agnes_client as ac_mod
    class NotConfigured:
        @classmethod
        def configured(cls): return False
        def __init__(self, **kw): pass
    monkeypatch.setattr(ac_mod, "AgnesVideoClient", NotConfigured)
    with pytest.raises(RuntimeError, match="Agnes Video 未配置"):
        await pipeline.render_one_scene(
            project_id="p1", scene=_scene(), idx=1, total_scenes=1, title="T",
            render_mode="agnes-video",
        )


# ---------------------------------------------------------------------------
# agnes_num_frames — dynamic frame count
# ---------------------------------------------------------------------------

def test_agnes_num_frames_basic():
    """3.5s * 24fps = 84 -> align to 8n+1 = 89."""
    assert pipeline.agnes_num_frames(3.5) == 89


def test_agnes_num_frames_minimum():
    """Duration of 0 should give minimum 9 frames (n=1)."""
    assert pipeline.agnes_num_frames(0) == 9


def test_agnes_num_frames_cap():
    """18s * 24 = 432 -> align to 8n+1 = 433."""
    assert pipeline.agnes_num_frames(18.0) == 433


def test_agnes_num_frames_over_cap():
    """>18s should still cap at 441."""
    assert pipeline.agnes_num_frames(30.0) == 441


def test_agnes_num_frames_exact_8n_plus_1():
    """8*10+1=81 frames -> exactly 81 (already valid)."""
    assert pipeline.agnes_num_frames(81 / 24) == 81


# ---------------------------------------------------------------------------
# probe_agnes_resolution — resolution cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_probe_agnes_resolution_caches_result(monkeypatch):
    """Second call returns cached value without hitting Agnes."""
    pipeline._AGNES_RESOLUTION_CACHE.clear()
    call_count = {"n": 0}
    import cn_social_agent.video.agnes_client as ac_mod
    class FakeProbeClient:
        @classmethod
        def configured(cls): return True
        def __init__(self, **kw): pass
        async def generate_to_file(self, prompt, dest, **kw):
            call_count["n"] += 1
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"x")
    monkeypatch.setattr(ac_mod, "AgnesVideoClient", FakeProbeClient)

    r1 = await pipeline.probe_agnes_resolution()
    r2 = await pipeline.probe_agnes_resolution()
    assert r1 == r2
    assert call_count["n"] == 1, "Only one Agnes call — second uses cache"


@pytest.mark.asyncio
async def test_probe_agnes_resolution_fallback_on_error(monkeypatch):
    """When 1080×1920 fails, falls back to 768×1344."""
    pipeline._AGNES_RESOLUTION_CACHE.clear()
    import cn_social_agent.video.agnes_client as ac_mod
    class FailClient:
        @classmethod
        def configured(cls): return True
        def __init__(self, **kw): pass
        async def generate_to_file(self, prompt, dest, **kw):
            if kw.get("width") == 1080:
                raise RuntimeError("resolution not supported")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"x")
    monkeypatch.setattr(ac_mod, "AgnesVideoClient", FailClient)

    result = await pipeline.probe_agnes_resolution()
    assert result == (768, 1344)


@pytest.mark.asyncio
async def test_probe_agnes_not_configured_returns_default(monkeypatch):
    """When Agnes not configured, returns default 768×1344."""
    pipeline._AGNES_RESOLUTION_CACHE.clear()
    import cn_social_agent.video.agnes_client as ac_mod
    class NotConfig:
        @classmethod
        def configured(cls): return False
    monkeypatch.setattr(ac_mod, "AgnesVideoClient", NotConfig)

    result = await pipeline.probe_agnes_resolution()
    assert result == (768, 1344)
