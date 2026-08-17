"""Derive a visible production plan from project / scenes / job state."""

from __future__ import annotations

from typing import Any, Optional

from cn_social_agent.video.pipeline import decode_script_bundle, delivery_snapshot
from cn_social_agent.video.presentation import (
    checkpoint_confirmed,
    get_checkpoints,
    is_presentation,
    presentation_dir,
)

STEP_DEFS = (
    ("topic", "选题"),
    ("angle", "类型"),
    ("brief", "要素"),
    ("script", "分镜"),
    ("l0", "草稿"),
    ("l1", "成片"),
)

ANGLE_LABELS = {
    "intro": "入门讲解",
    "compare": "对比选型",
    "deep_analysis": "深度分析",
    "idea": "观点短评",
    "general": "通用",
}

PRESENTATION_STEP_DEFS = (
    ("topic", "选题"),
    ("outline", "大纲"),
    ("build", "构建"),
    ("audio", "音频"),
    ("record", "录屏"),
    ("publish", "发布"),
)


def build_production_plan(
    project: dict[str, Any],
    scenes: Optional[list[dict[str, Any]]] = None,
    job: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return production_plan for API / UI.

    Each step: {id, label, status: pending|active|done|failed, detail}
    """
    plain, meta = decode_script_bundle(project.get("script") or "")
    if is_presentation(project, meta):
        return _build_presentation_plan(project, meta, job, plain=plain)

    scenes = list(scenes or [])
    job = job or {}
    delivery = delivery_snapshot(project)

    status = (project.get("status") or "").lower()
    job_status = (job.get("status") or "").lower()
    fail_reason = (
        (job.get("fail_reason") or "")
        or (delivery.get("fail_reason") or "")
        or (meta.get("fail_reason") or "")
    ).strip()

    topic = (project.get("topic") or "").strip()
    angle = (meta.get("content_angle") or "").strip()
    audience = (meta.get("audience") or "").strip()
    scene = (meta.get("scene_setting") or "").strip()
    level = (delivery.get("delivery_level") or meta.get("delivery_level") or "").lower()
    has_output = bool(project.get("output_path"))

    topic_done = bool(topic)
    angle_done = bool(angle)
    brief_done = bool(audience or scene)
    script_ready = len(scenes) > 0
    confirmed = bool(meta.get("storyboard_confirmed"))
    script_done = script_ready and confirmed
    l1_done = has_output and status == "done" and level == "l1"
    l0_done = l1_done or (has_output and status == "done" and level in ("l0", ""))

    job_level = (job.get("delivery_level") or "").lower()
    rendering = job_status == "rendering" or status == "rendering"
    failed = status == "failed" or job_status == "failed"

    done_flags = {
        "topic": topic_done,
        "angle": angle_done,
        "brief": brief_done,
        "script": script_done,
        "l0": l0_done,
        "l1": l1_done,
    }
    details = {
        "topic": topic[:40],
        "angle": ANGLE_LABELS.get(angle, angle) if angle else "",
        "brief": (
            "+".join([x for x in (("受众" if audience else ""), ("场景" if scene else "")) if x])
            or ""
        ),
        "script": (
            f"{len(scenes)} 镜·已确认"
            if script_done
            else (f"{len(scenes)} 镜·待确认" if script_ready else "")
        ),
        "l0": "可预览" if l0_done else ("渲染中" if rendering and job_level != "l1" else ("先确认分镜" if script_ready and not confirmed else "待生成")),
        "l1": "可下载" if l1_done else ("升级中" if rendering and job_level == "l1" else "可选"),
    }

    first_open: Optional[str] = None
    for sid, _ in STEP_DEFS:
        if not done_flags[sid]:
            first_open = sid
            break

    steps: list[dict[str, Any]] = []
    for sid, label in STEP_DEFS:
        st = "pending"
        detail = details[sid]

        if done_flags[sid]:
            st = "done"
        elif sid == "l0" and rendering and job_level != "l1":
            st = "active"
            detail = (job.get("message") or "渲染中")[:60]
        elif sid == "l1" and rendering and job_level == "l1":
            st = "active"
            detail = (job.get("message") or "升级中")[:60]
        elif sid == "l0" and failed and not l0_done and job_level != "l1" and level != "l1":
            st = "failed"
            detail = (fail_reason or "草稿失败")[:80]
        elif sid == "l1" and failed and (job_level == "l1" or level == "l1"):
            st = "failed"
            detail = (fail_reason or "成片失败")[:80]
        elif sid == first_open:
            st = "active"

        steps.append({"id": sid, "label": label, "status": st, "detail": detail})

    done_n = sum(1 for s in steps if s["status"] == "done")
    current = next(
        (s["id"] for s in steps if s["status"] in ("active", "failed")),
        "l1" if l1_done else (first_open or "topic"),
    )
    return {
        "steps": steps,
        "done_count": done_n,
        "total": len(steps),
        "progress_label": f"{done_n}/{len(steps)}",
        "current": current,
        "fail_reason": fail_reason,
        "delivery_level": level or None,
        "project_status": status,
        "track": "koubo",
    }


def _build_presentation_plan(
    project: dict[str, Any],
    meta: dict[str, Any],
    job: Optional[dict[str, Any]] = None,
    *,
    plain: str = "",
) -> dict[str, Any]:
    job = job or {}
    status = (project.get("status") or "").lower()
    job_status = (job.get("status") or "").lower()
    fail_reason = (
        (job.get("fail_reason") or "")
        or (meta.get("fail_reason") or "")
    ).strip()

    topic = (project.get("topic") or "").strip()
    outline = (meta.get("outline") or "").strip()
    script_body = (plain or meta.get("full_script") or "").strip()
    a1 = checkpoint_confirmed(meta, "a1")
    b = checkpoint_confirmed(meta, "b")
    b_block = get_checkpoints(meta).get("b") or {}
    synthesize = bool(b_block.get("synthesize_audio")) if isinstance(b_block, dict) else False
    pid = str(project.get("id") or "")
    root = presentation_dir(pid) if pid else None
    scaffolded = bool(meta.get("presentation_path")) or (
        bool(root and root.is_dir() and (root / "package.json").is_file())
    )
    built = bool(root and (root / "dist" / "index.html").is_file()) or bool(
        meta.get("presentation_built")
    )
    audio_dir = root / "public" / "audio" if root else None
    has_audio = bool(meta.get("audio_ready")) or (
        bool(audio_dir and audio_dir.is_dir()) and any(audio_dir.glob("*.mp3"))
    )
    has_output = bool(project.get("output_path"))
    pub = meta.get("publish") if isinstance(meta.get("publish"), dict) else {}
    published = (pub.get("status") or "") in ("published", "draft")

    topic_done = bool(topic)
    outline_done = bool(outline and script_body and a1)
    build_done = scaffolded and built and b
    if b and not synthesize:
        audio_done = True
        audio_detail = "跳过 TTS"
    elif has_audio:
        audio_done = True
        audio_detail = "已合成"
    else:
        audio_done = False
        audio_detail = "待合成" if b and synthesize else ("先完成检查点 B" if not b else "")
    record_done = has_output
    publish_done = published

    done_flags = {
        "topic": topic_done,
        "outline": outline_done,
        "build": build_done,
        "audio": audio_done if b else False,
        "record": record_done,
        "publish": publish_done,
    }
    details = {
        "topic": topic[:40],
        "outline": "A1 已确认" if outline_done else ("待确认 A1" if (outline or script_body) else "待写大纲"),
        "build": (
            "可预览"
            if build_done
            else (
                "构建中"
                if job_status in ("building", "rendering")
                else ("待构建" if a1 else "先完成 A1")
            )
        ),
        "audio": audio_detail,
        "record": "已导入" if record_done else ("OBS 录制后导入" if build_done else ""),
        "publish": (pub.get("status") or "") if publish_done else ("可发抖音" if record_done else ""),
    }

    first_open: Optional[str] = None
    for sid, _ in PRESENTATION_STEP_DEFS:
        if not done_flags[sid]:
            first_open = sid
            break

    steps: list[dict[str, Any]] = []
    for sid, label in PRESENTATION_STEP_DEFS:
        st = "pending"
        detail = details[sid]
        if done_flags[sid]:
            st = "done"
        elif sid == "build" and job_status in ("building", "rendering"):
            st = "active"
            detail = (job.get("message") or "构建中")[:60]
        elif sid == "build" and (status == "failed" or job_status == "failed") and not build_done:
            st = "failed"
            detail = (fail_reason or "构建失败")[:80]
        elif sid == first_open:
            st = "active"
        steps.append({"id": sid, "label": label, "status": st, "detail": detail})

    done_n = sum(1 for s in steps if s["status"] == "done")
    current = next(
        (s["id"] for s in steps if s["status"] in ("active", "failed")),
        first_open or "topic",
    )
    return {
        "steps": steps,
        "done_count": done_n,
        "total": len(steps),
        "progress_label": f"{done_n}/{len(steps)}",
        "current": current,
        "fail_reason": fail_reason,
        "delivery_level": None,
        "project_status": status,
        "track": "presentation",
        "aspect": meta.get("aspect") or "16:9",
        "phase": meta.get("phase") or "content",
    }
