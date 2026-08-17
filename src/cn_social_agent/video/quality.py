"""L1 成片质检 v0 — black frame / motion / A-V duration."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class QualityResult:
    passed: bool
    reasons: list[str]
    metrics: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "reasons": self.reasons,
            "metrics": self.metrics,
        }


def _run_ffprobe(path: Path) -> dict[str, Any]:
    r = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,duration,avg_frame_rate,nb_frames",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        return {}
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return {}


def _sample_frame_stats(path: Path, *, samples: int = 8) -> dict[str, float]:
    """Extract a few frames as raw rgb24 and compute brightness + pairwise MAD."""
    probe = _run_ffprobe(path)
    dur = 0.0
    try:
        dur = float((probe.get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        dur = 0.0
    if dur <= 0.4:
        dur = 3.0

    times = [dur * (i + 0.5) / samples for i in range(samples)]
    frames: list[bytes] = []
    w, h = 160, 284  # small probe resolution
    for t in times:
        r = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{t:.3f}",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-s",
                f"{w}x{h}",
                "pipe:1",
            ],
            capture_output=True,
            check=False,
        )
        if r.returncode == 0 and r.stdout:
            frames.append(r.stdout)

    if len(frames) < 2:
        return {"brightness": 0.0, "motion_mad": 0.0, "samples": float(len(frames))}

    def mean_brightness(buf: bytes) -> float:
        # average of first channel-ish: all bytes / 255
        if not buf:
            return 0.0
        return sum(buf) / (len(buf) * 255.0)

    brights = [mean_brightness(f) for f in frames]
    mads = []
    for a, b in zip(frames, frames[1:]):
        n = min(len(a), len(b))
        if n == 0:
            continue
        mads.append(sum(abs(a[i] - b[i]) for i in range(n)) / (n * 255.0))

    return {
        "brightness": sum(brights) / len(brights),
        "motion_mad": sum(mads) / len(mads) if mads else 0.0,
        "samples": float(len(frames)),
    }


def check_final_video(
    path: Path,
    *,
    expected_audio_seconds: Optional[float] = None,
    min_brightness: float = 0.06,
    min_motion_mad: float = 0.012,
    max_av_skew: float = 0.45,
) -> QualityResult:
    """P0 gate for L1 成片. Local L0 drafts should skip this."""
    reasons: list[str] = []
    metrics: dict[str, Any] = {}

    if not path.is_file():
        return QualityResult(False, ["output file missing"], {})

    probe = _run_ffprobe(path)
    metrics["probe_ok"] = bool(probe)
    try:
        vdur = float((probe.get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        vdur = 0.0
    metrics["video_duration"] = vdur

    streams = probe.get("streams") or []
    has_a = any(s.get("codec_type") == "audio" for s in streams)
    has_v = any(s.get("codec_type") == "video" for s in streams)
    if not has_v:
        reasons.append("missing video stream")
    if not has_a:
        reasons.append("missing audio stream")

    stats = _sample_frame_stats(path)
    metrics.update(stats)
    if stats.get("brightness", 0) < min_brightness:
        reasons.append(
            f"黑场占比过高（平均亮度 {stats.get('brightness', 0):.3f} < {min_brightness}）"
        )
    if stats.get("motion_mad", 0) < min_motion_mad:
        reasons.append(
            f"画面近似静帧（运动幅度 {stats.get('motion_mad', 0):.4f} < {min_motion_mad}）"
        )

    if expected_audio_seconds is not None and vdur > 0:
        skew = abs(vdur - float(expected_audio_seconds))
        metrics["av_skew"] = skew
        metrics["expected_audio_seconds"] = float(expected_audio_seconds)
        # Allow 8% or 0.8s — concat/fade can shorten vs TTS sum
        tol = max(max_av_skew, float(expected_audio_seconds) * 0.08, 0.8)
        metrics["av_tol"] = tol
        if skew > tol:
            reasons.append(
                f"音画时长偏差过大（|{vdur:.2f}-{expected_audio_seconds:.2f}|={skew:.2f}s）"
            )

    # Prefer in-file A/V stream skew when both present
    try:
        a_durs = [
            float(s.get("duration"))
            for s in streams
            if s.get("codec_type") == "audio" and s.get("duration")
        ]
        if a_durs and vdur > 0:
            ad = a_durs[0]
            skew_in = abs(vdur - ad)
            metrics["av_skew_infile"] = skew_in
            if skew_in > max(max_av_skew, 0.8):
                reasons.append(
                    f"文件内音画不同步（v={vdur:.2f}s a={ad:.2f}s）"
                )
    except (TypeError, ValueError):
        pass

    # Deduplicate reasons
    uniq: list[str] = []
    for r in reasons:
        if r not in uniq:
            uniq.append(r)
    return QualityResult(passed=not uniq, reasons=uniq, metrics=metrics)


def suggest_scene_rerenders(
    project_id: str,
    scenes: list[dict[str, Any]],
    *,
    min_brightness: float = 0.06,
    min_motion_mad: float = 0.012,
    deep: bool = False,
) -> list[dict[str, Any]]:
    """Per-scene quality hints.

    Fast path (default): only missing-clip / meta tips — safe for project open & poll.
    Deep path: ffprobe + frame sampling (slow; use only for explicit quality review).
    """
    from cn_social_agent.video.pipeline import project_dir, unpack_scene_meta

    root = project_dir(project_id)
    tips: list[dict[str, Any]] = []
    for sc in scenes:
        num = int(sc.get("scene_num") or 0)
        if num <= 0:
            continue
        clip = root / f"scene_{num}.mp4"
        meta = unpack_scene_meta(str(sc.get("image_path") or ""))
        role = meta.get("role") or "value"
        if not clip.is_file():
            tips.append(
                {
                    "scene_num": num,
                    "role": role,
                    "reason": "缺少分镜片段，需重渲",
                    "priority": "high",
                    "suggested_delivery": "l0",
                }
            )
            continue
        if not deep:
            if role in ("hook", "cta") and meta.get("scene_render_mode") != "agnes-video":
                tips.append(
                    {
                        "scene_num": num,
                        "role": role,
                        "reason": "钩子/行动镜建议升级成片画面（L1）",
                        "priority": "medium",
                        "suggested_delivery": "l1",
                    }
                )
            continue
        expected = float(sc.get("tts_duration_seconds") or 0) or None
        gate = check_final_video(
            clip,
            expected_audio_seconds=expected,
            min_brightness=min_brightness,
            min_motion_mad=min_motion_mad,
        )
        if gate.passed:
            if role in ("hook", "cta") and meta.get("scene_render_mode") != "agnes-video":
                tips.append(
                    {
                        "scene_num": num,
                        "role": role,
                        "reason": "钩子/行动镜建议升级成片画面（L1）",
                        "priority": "medium",
                        "suggested_delivery": "l1",
                    }
                )
            continue
        tips.append(
            {
                "scene_num": num,
                "role": role,
                "reason": "；".join(gate.reasons) or "质检未通过",
                "priority": "high",
                "suggested_delivery": "l1" if role in ("hook", "cta") else "l0",
                "metrics": gate.metrics,
            }
        )
    return tips
