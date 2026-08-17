"""Presentation dual QC — content gate + final video gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from cn_social_agent.video.presentation import (
    checkpoint_confirmed,
    dist_dir,
    load_content_json,
    presentation_dir,
)
from cn_social_agent.action_errors import presentation_quality_items
from cn_social_agent.video.presentation_content import depth_report
from cn_social_agent.video.quality import QualityResult, check_final_video
from cn_social_agent.video.verification import verification_report


def _load_narrations_doc(project_id: str) -> dict[str, Any]:
    root = presentation_dir(project_id)
    for rel in ("dist/narrations.json", "public/narrations.json"):
        path = root / rel
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if isinstance(data, dict):
            return data
    return {}


def _final_path(project_id: str, output_path: str = "") -> Optional[Path]:
    if output_path:
        p = Path(output_path)
        if p.is_file():
            return p
    root = presentation_dir(project_id)
    for name in ("final.mp4", "final.webm", "final.mkv"):
        cand = root / name
        if cand.is_file():
            return cand
    return None


def run_content_qc(project_id: str, *, meta: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Gate A: 实测弧线文稿 + 舞台 + 旁白时间轴。"""
    meta = meta or {}
    issues: list[str] = []
    content = load_content_json(project_id)
    depth = depth_report(content if isinstance(content, dict) else {})
    if not depth.get("ok"):
        failed = [k for k, v in (depth.get("checks") or {}).items() if not v]
        issues.append("文稿未达标：" + ("、".join(failed[:6]) or "depth"))

    built = (dist_dir(project_id) / "index.html").is_file()
    if not built:
        issues.append("舞台未构建")

    a1 = checkpoint_confirmed(meta, "a1")
    if not a1:
        issues.append("未确认 A1（大纲/口播）")

    vrep = verification_report(content if isinstance(content, dict) else {})
    if not vrep.get("ok"):
        if vrep.get("missing_roles"):
            issues.append("demo 验证未声明：" + "、".join(vrep["missing_roles"]))
        elif vrep.get("declared", 0) == 0:
            issues.append("缺少 demo 验证（verify.command）")
        elif vrep.get("pending"):
            issues.append(f"有 {vrep['pending']} 步验证未在沙箱运行")
        elif vrep.get("unavailable"):
            issues.append(f"有 {vrep['unavailable']} 步验证因 Docker 不可用而跳过")
        elif vrep.get("failed"):
            issues.append(f"有 {vrep['failed']} 步验证未通过：" + "、".join(vrep.get("fail_keys", [])[:4]))

    narr = _load_narrations_doc(project_id)
    narr_qc = narr.get("qc") if isinstance(narr.get("qc"), dict) else None
    total_ms = int(narr.get("total_ms") or meta.get("narration_total_ms") or 0)
    if narr_qc is None and meta.get("audio_ready"):
        issues.append("已标音频就绪但缺少时间轴质检")
    elif isinstance(narr_qc, dict) and not narr_qc.get("ok"):
        for i in (narr_qc.get("issues") or [])[:3]:
            issues.append(f"旁白时间轴：{i}")
        if not (narr_qc.get("issues") or []):
            issues.append("旁白时间轴未通过")

    checks = {
        "depth_ok": bool(depth.get("ok")),
        "stage_built": built,
        "a1_confirmed": a1,
        "demo_verify_pass": bool(vrep.get("ok")),
        "narration_timeline_ok": True,
    }
    if meta.get("audio_ready") or narr_qc is not None:
        checks["narration_timeline_ok"] = bool(
            isinstance(narr_qc, dict) and narr_qc.get("ok")
        )

    ok = all(checks.values())
    return {
        "ok": ok,
        "checks": checks,
        "issues": issues[:10],
        "stats": {
            **(depth.get("stats") or {}),
            "narration_total_ms": total_ms,
            "narration_steps": len(narr.get("timeline") or []),
        },
        "depth": depth,
        "narration_qc": narr_qc,
        "verification": vrep,
    }


def run_final_qc(
    project_id: str,
    *,
    output_path: str = "",
    expected_seconds: Optional[float] = None,
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Gate B: 导入成片的音画/黑场/时长对齐。"""
    meta = meta or {}
    path = _final_path(project_id, output_path)
    if path is None:
        return {
            "ok": False,
            "passed": False,
            "reasons": ["尚未导入成片"],
            "metrics": {},
            "path": "",
        }

    exp = expected_seconds
    if exp is None:
        narr = _load_narrations_doc(project_id)
        total_ms = int(narr.get("total_ms") or meta.get("narration_total_ms") or 0)
        if total_ms > 0:
            exp = total_ms / 1000.0

    # Screen-recordings of slide decks move less than AGNES footage
    gate: QualityResult = check_final_video(
        path,
        expected_audio_seconds=exp,
        min_brightness=0.05,
        min_motion_mad=0.008,
        max_av_skew=1.2,
    )
    # Extra: file too short vs timeline (OBS cut early)
    reasons = list(gate.reasons)
    metrics = dict(gate.metrics)
    metrics["path"] = str(path)
    if exp and exp >= 8:
        vdur = float(metrics.get("video_duration") or 0)
        if vdur > 0 and vdur < exp * 0.75:
            reasons.append(
                f"成片偏短（{vdur:.1f}s < 旁白时间轴 {exp:.1f}s 的 75%）"
            )
        if vdur > 0 and vdur > exp * 1.6 + 8:
            reasons.append(
                f"成片偏长（{vdur:.1f}s ≫ 旁白时间轴 {exp:.1f}s，可能未停录）"
            )

    uniq: list[str] = []
    for r in reasons:
        if r not in uniq:
            uniq.append(r)
    passed = not uniq
    return {
        "ok": passed,
        "passed": passed,
        "reasons": uniq,
        "metrics": metrics,
        "path": str(path),
        "expected_seconds": exp,
    }


def run_dual_qc(
    project_id: str,
    *,
    meta: Optional[dict[str, Any]] = None,
    output_path: str = "",
) -> dict[str, Any]:
    """Content + final dual gate for presentation track."""
    meta = meta or {}
    content = run_content_qc(project_id, meta=meta)
    final = run_final_qc(
        project_id,
        output_path=output_path,
        meta=meta,
    )
    has_final = bool(final.get("path"))
    ok = bool(content.get("ok")) and (bool(final.get("ok")) if has_final else False)
    if not has_final:
        hint = (
            "内容门禁"
            + ("通过" if content.get("ok") else "未过")
            + "；请录屏/导入成片后再跑成片门禁"
        )
    elif ok:
        hint = "双质检通过：内容与成片均达标"
    else:
        bits = []
        if not content.get("ok"):
            bits.append("内容：" + "；".join((content.get("issues") or [])[:2] or ["未过"]))
        if not final.get("ok"):
            bits.append("成片：" + "；".join((final.get("reasons") or [])[:2] or ["未过"]))
        hint = "双质检未过 — " + " | ".join(bits)
    items = presentation_quality_items(
        content,
        final_qc=final,
        verification=content.get("verification") if isinstance(content, dict) else None,
    )
    blockers = [
        i["label"] + (f"（{i['detail']}）" if i.get("detail") else "")
        for i in items
        if i.get("status") == "fail"
    ]
    return {
        "ok": ok,
        "content": content,
        "final": final,
        "has_final": has_final,
        "hint": hint,
        "quality_items": items,
        "blockers": blockers,
    }
