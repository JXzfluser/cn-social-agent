"""P0 quality gate unit tests (mocked ffprobe / frame sampling)."""

from __future__ import annotations

from pathlib import Path

import cn_social_agent.video.quality as quality


def test_missing_file_fails(tmp_path: Path):
    r = quality.check_final_video(tmp_path / "nope.mp4")
    assert r.passed is False
    assert any("missing" in x for x in r.reasons)


def test_black_frame_fails(monkeypatch, tmp_path: Path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fake")

    monkeypatch.setattr(
        quality,
        "_run_ffprobe",
        lambda _p: {
            "format": {"duration": "10.0"},
            "streams": [
                {"codec_type": "video", "duration": "10.0"},
                {"codec_type": "audio", "duration": "10.0"},
            ],
        },
    )
    monkeypatch.setattr(
        quality,
        "_sample_frame_stats",
        lambda _p, samples=8: {"brightness": 0.01, "motion_mad": 0.05, "samples": 8.0},
    )
    r = quality.check_final_video(path, expected_audio_seconds=10.0)
    assert r.passed is False
    assert any("黑场" in x for x in r.reasons)


def test_static_frame_fails(monkeypatch, tmp_path: Path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fake")
    monkeypatch.setattr(
        quality,
        "_run_ffprobe",
        lambda _p: {
            "format": {"duration": "8.0"},
            "streams": [
                {"codec_type": "video", "duration": "8.0"},
                {"codec_type": "audio", "duration": "8.0"},
            ],
        },
    )
    monkeypatch.setattr(
        quality,
        "_sample_frame_stats",
        lambda _p, samples=8: {"brightness": 0.4, "motion_mad": 0.001, "samples": 8.0},
    )
    r = quality.check_final_video(path, expected_audio_seconds=8.0)
    assert r.passed is False
    assert any("静帧" in x for x in r.reasons)


def test_av_skew_fails(monkeypatch, tmp_path: Path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fake")
    monkeypatch.setattr(
        quality,
        "_run_ffprobe",
        lambda _p: {
            "format": {"duration": "12.0"},
            "streams": [
                {"codec_type": "video", "duration": "12.0"},
                {"codec_type": "audio", "duration": "12.0"},
            ],
        },
    )
    monkeypatch.setattr(
        quality,
        "_sample_frame_stats",
        lambda _p, samples=8: {"brightness": 0.4, "motion_mad": 0.05, "samples": 8.0},
    )
    r = quality.check_final_video(path, expected_audio_seconds=5.0, max_av_skew=0.45)
    assert r.passed is False
    assert any("音画时长" in x for x in r.reasons)


def test_healthy_clip_passes(monkeypatch, tmp_path: Path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fake")
    monkeypatch.setattr(
        quality,
        "_run_ffprobe",
        lambda _p: {
            "format": {"duration": "10.0"},
            "streams": [
                {"codec_type": "video", "duration": "10.0"},
                {"codec_type": "audio", "duration": "10.0"},
            ],
        },
    )
    monkeypatch.setattr(
        quality,
        "_sample_frame_stats",
        lambda _p, samples=8: {"brightness": 0.35, "motion_mad": 0.04, "samples": 8.0},
    )
    r = quality.check_final_video(path, expected_audio_seconds=10.0)
    assert r.passed is True
    assert r.reasons == []


def test_apply_template_defaults_product_update():
    from cn_social_agent.video.pipeline import apply_template_defaults, list_video_styles

    d = apply_template_defaults(template_id="product_update")
    assert d["target_seconds"] == 15
    assert d["content_angle"] == "intro"
    styles = list_video_styles()
    assert styles["default_seconds"] == 15
    ids = {t["id"] for t in styles["templates"]}
    assert ids == {"product_update", "tech_rant", "tutorial"}


# ---------------------------------------------------------------------------
# P1/P2 quality gate tests
# ---------------------------------------------------------------------------

def test_scene_quality_passes_on_valid_clip(monkeypatch, tmp_path):
    import json
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fake")
    monkeypatch.setattr(
        quality,
        "_run_ffprobe",
        lambda _p: {
            "format": {"duration": "3.5"},
            "streams": [
                {"codec_type": "video", "width": 1080, "height": 1920, "duration": "3.5"},
                {"codec_type": "audio", "duration": "3.5"},
            ],
        },
    )
    import json
    scene = {"scene_num": 1, "image_path": json.dumps({"role": "hook", "on_screen": "标题"})}
    r = quality.check_scene_quality(scene, path, role="hook")
    assert r.passed is True
    assert r.metrics["width"] == 1080
    assert r.metrics["height"] == 1920
    assert r.metrics["has_subtitle"] is True


def test_scene_quality_fails_on_bad_resolution(monkeypatch, tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fake")
    monkeypatch.setattr(
        quality,
        "_run_ffprobe",
        lambda _p: {
            "format": {"duration": "3.0"},
            "streams": [
                {"codec_type": "video", "width": 640, "height": 480, "duration": "3.0"},
                {"codec_type": "audio", "duration": "3.0"},
            ],
        },
    )
    scene = {"scene_num": 1, "image_path": ""}
    r = quality.check_scene_quality(scene, path, role="value")
    assert r.passed is False
    assert any("分辨率" in x for x in r.reasons)


def test_scene_quality_fails_on_hook_too_long(monkeypatch, tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fake")
    monkeypatch.setattr(
        quality,
        "_run_ffprobe",
        lambda _p: {
            "format": {"duration": "8.0"},
            "streams": [
                {"codec_type": "video", "width": 1080, "height": 1920, "duration": "8.0"},
                {"codec_type": "audio", "duration": "8.0"},
            ],
        },
    )
    scene = {"scene_num": 1, "image_path": ""}
    r = quality.check_scene_quality(scene, path, role="hook")
    assert r.passed is False
    assert any("钩子时长" in x for x in r.reasons)


def test_scene_quality_warns_on_bad_aspect_ratio(monkeypatch, tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fake")
    monkeypatch.setattr(
        quality,
        "_run_ffprobe",
        lambda _p: {
            "format": {"duration": "3.0"},
            "streams": [
                {"codec_type": "video", "width": 1920, "height": 1080, "duration": "3.0"},
                {"codec_type": "audio", "duration": "3.0"},
            ],
        },
    )
    scene = {"scene_num": 1, "image_path": ""}
    r = quality.check_scene_quality(scene, path, role="value")
    assert r.passed is False
    assert any("宽高比" in x for x in r.reasons)


def test_scene_quality_missing_clip():
    scene = {"scene_num": 1, "image_path": ""}
    r = quality.check_scene_quality(scene, Path("/no/such/file.mp4"), role="value")
    assert r.passed is False
    assert any("missing" in x for x in r.reasons)
