"""Tests for presentation narration timeline + QC."""

from __future__ import annotations

from cn_social_agent.video.presentation import (
    build_timeline_qc,
    estimate_narration_ms,
    slide_narration_text,
)


def test_estimate_narration_ms_floor_and_scale():
    assert estimate_narration_ms("") == 2200
    assert estimate_narration_ms("短") == 2200
    assert estimate_narration_ms("甲" * 30) == 30 * 120


def test_slide_narration_text_prefers_narration():
    assert slide_narration_text({"narration": "口播", "body": "正文", "title": "题"}) == "口播"
    assert slide_narration_text({"body": "正文", "title": "题"}) == "正文"
    assert slide_narration_text({"title": "题"}) == "题"


def test_timeline_qc_passes_complete():
    steps = {
        "0:0": {"text": "a" * 20, "audio": "./audio/a.mp3", "duration_ms": 2400},
        "0:1": {"text": "b" * 20, "audio": "./audio/b.mp3", "duration_ms": 3000},
    }
    timeline = [
        {"key": "0:0", **steps["0:0"], "start_ms": 0},
        {"key": "0:1", **steps["0:1"], "start_ms": 2400},
    ]
    qc = build_timeline_qc(total_slides=2, steps=steps, timeline=timeline)
    assert qc["ok"] is True
    assert qc["checks"]["all_text_has_audio"] is True


def test_timeline_qc_flags_missing_audio_and_coverage():
    steps = {
        "0:0": {"text": "只有文案", "duration_ms": 2400},
    }
    qc = build_timeline_qc(total_slides=4, steps=steps, timeline=[])
    assert qc["ok"] is False
    assert qc["checks"]["all_text_has_audio"] is False
    assert qc["checks"]["coverage_ge_half"] is False
    assert qc["checks"]["has_timeline"] is False
    assert any("缺音频" in i for i in qc["issues"])
