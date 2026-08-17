"""Durable render progress (wbmeta) tests."""

from __future__ import annotations

from cn_social_agent.video.pipeline import (
    apply_render_progress,
    clear_render_progress,
    decode_script_bundle,
    encode_script_bundle,
    job_from_wbmeta,
    merge_script_meta,
)


def test_apply_and_clear_render_progress_roundtrip():
    script = encode_script_bundle(
        {
            "full_script": "口播正文",
            "cover_hook": "钩子",
            "delivery_level": "l1",
            "render_mode": "agnes-video",
        }
    )
    patched = apply_render_progress(
        script,
        progress=42,
        message="scene 3/7",
        scene_i=3,
        scene_n=7,
        started_at="2026-08-16T12:00:00Z",
    )
    plain, meta = decode_script_bundle(patched)
    assert plain.startswith("口播正文")
    assert meta["render_progress"] == 42
    assert meta["render_message"] == "scene 3/7"
    assert meta["render_scene_i"] == 3
    assert meta["render_scene_n"] == 7
    assert meta["render_started_at"] == "2026-08-16T12:00:00Z"
    assert meta["delivery_level"] == "l1"

    cleared = clear_render_progress(patched)
    _plain2, meta2 = decode_script_bundle(cleared)
    assert "render_progress" not in meta2
    assert "render_message" not in meta2
    assert meta2["delivery_level"] == "l1"


def test_job_from_wbmeta_when_rendering():
    script = apply_render_progress(
        merge_script_meta(
            encode_script_bundle({"full_script": "x", "delivery_level": "l1"}),
            render_mode="agnes-video",
        ),
        progress=55,
        message="后台升级成片中…",
        scene_i=2,
        scene_n=4,
    )
    project = {"status": "rendering", "script": script}
    job = job_from_wbmeta(project, {"delivery_level": "l1", "render_mode": "agnes-video"})
    assert job is not None
    assert job["status"] == "rendering"
    assert job["progress"] == 55
    assert job["message"] == "后台升级成片中…"
    assert job["scene_i"] == 2
    assert job["scene_n"] == 4
    assert job["from_wbmeta"] is True


def test_job_from_wbmeta_skips_when_not_rendering():
    script = apply_render_progress(
        encode_script_bundle({"full_script": "x"}),
        progress=80,
        message="almost",
    )
    assert job_from_wbmeta({"status": "done", "script": script}) is None
    assert job_from_wbmeta({"status": "rendering", "script": "plain only"}) is None
