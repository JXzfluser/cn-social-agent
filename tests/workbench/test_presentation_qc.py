"""Tests for presentation dual QC."""

from __future__ import annotations

from unittest.mock import patch

from cn_social_agent.video.presentation_qc import (
    run_content_qc,
    run_dual_qc,
    run_final_qc,
)
from cn_social_agent.video.quality import QualityResult


def test_final_qc_missing_file():
    out = run_final_qc("no-such-project-xyz")
    assert out["ok"] is False
    assert "尚未导入成片" in out["reasons"][0]


def test_content_qc_empty_project(tmp_path):
    pid = "qc-empty"
    with patch(
        "cn_social_agent.video.presentation_qc.presentation_dir",
        return_value=tmp_path / pid,
    ), patch(
        "cn_social_agent.video.presentation_qc.dist_dir",
        return_value=tmp_path / pid / "dist",
    ), patch(
        "cn_social_agent.video.presentation_qc.load_content_json",
        return_value={"title": "t", "chapters": []},
    ):
        (tmp_path / pid).mkdir(parents=True)
        out = run_content_qc(pid, meta={})
    assert out["ok"] is False
    assert out["checks"]["depth_ok"] is False
    assert out["checks"]["stage_built"] is False
    assert out["checks"]["a1_confirmed"] is False


def test_content_qc_passes_when_depth_and_a1_and_built(tmp_path):
    from tests.workbench.test_presentation_content import _rich_doc
    from cn_social_agent.video.presentation_content import normalize_presentation_doc

    doc = normalize_presentation_doc(_rich_doc())
    # Simulate a completed sandbox run so the verify gate is satisfied.
    for ch in doc["chapters"]:
        for sl in ch["slides"]:
            if isinstance(sl.get("verify"), dict):
                sl["verify"]["status"] = "pass"
    pid = "qc-rich"
    root = tmp_path / pid
    dist = root / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    with patch(
        "cn_social_agent.video.presentation_qc.presentation_dir",
        return_value=root,
    ), patch(
        "cn_social_agent.video.presentation_qc.dist_dir",
        return_value=dist,
    ), patch(
        "cn_social_agent.video.presentation_qc.load_content_json",
        return_value=doc,
    ):
        out = run_content_qc(
            pid,
            meta={"checkpoints": {"a1": {"confirmed": True}}},
        )
    assert out["checks"]["depth_ok"] is True
    assert out["checks"]["stage_built"] is True
    assert out["checks"]["a1_confirmed"] is True
    assert out["ok"] is True


def test_dual_qc_without_final_not_ok_overall():
    with patch(
        "cn_social_agent.video.presentation_qc.run_content_qc",
        return_value={"ok": True, "issues": [], "checks": {}},
    ), patch(
        "cn_social_agent.video.presentation_qc.run_final_qc",
        return_value={
            "ok": False,
            "passed": False,
            "reasons": ["尚未导入成片"],
            "metrics": {},
            "path": "",
        },
    ):
        dual = run_dual_qc("x", meta={})
    assert dual["content"]["ok"] is True
    assert dual["has_final"] is False
    assert dual["ok"] is False
    assert "导入成片" in dual["hint"]


def test_final_qc_uses_check_final_video(tmp_path):
    vid = tmp_path / "final.mp4"
    vid.write_bytes(b"fake")
    with patch(
        "cn_social_agent.video.presentation_qc._final_path",
        return_value=vid,
    ), patch(
        "cn_social_agent.video.presentation_qc.check_final_video",
        return_value=QualityResult(
            passed=True,
            reasons=[],
            metrics={"video_duration": 42.0, "brightness": 0.2, "motion_mad": 0.05},
        ),
    ), patch(
        "cn_social_agent.video.presentation_qc._load_narrations_doc",
        return_value={"total_ms": 40000},
    ):
        out = run_final_qc("p", output_path=str(vid), meta={})
    assert out["ok"] is True
    assert out["expected_seconds"] == 40.0
