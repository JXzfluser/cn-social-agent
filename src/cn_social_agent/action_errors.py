"""Classify raw exception / status strings into actionable UI cards.

The workbench historically dumped ``RuntimeError: cmd failed (1): …`` into
``.status.err`` lines; users then pasted the same string into chat. This module
turns those strings into ``{code, title, reason, actions}`` so the UI can show
「怎么修」instead of raw stderr.
"""

from __future__ import annotations

import re
from typing import Any, Optional

# (code, pattern, title, reason_template, actions)
# reason_template may use ``{detail}`` for a short excerpt of the original msg.
_RULES: list[tuple[str, re.Pattern[str], str, str, list[dict[str, str]]]] = [
    (
        "edge_tts_network",
        re.compile(
            r"edge-tts|NoAudioReceived|语音合成失败",
            re.I,
        ),
        "语音合成失败",
        "连不上 Microsoft TTS，或本机 edge-tts CLI 与当前 Python 环境不一致。",
        [
            {"id": "retry_tts_api", "label": "改用内置 API 重试"},
            {"id": "retry", "label": "再试一次"},
        ],
    ),
    (
        "agnes_queue",
        re.compile(r"video_queue_full|队列已满|queue is full", re.I),
        "Agnes 视频队列已满",
        "云端排队过载。可稍后重试本镜，或先用本地 L0 出片。",
        [
            {"id": "retry", "label": "稍后重试"},
            {"id": "use_local_l0", "label": "改用本地渲染"},
        ],
    ),
    (
        "missing_scene",
        re.compile(r"缺少分镜片段|scene_\d+\.mp4", re.I),
        "缺少分镜片段",
        "成片拼接时找不到某镜 mp4。请先完整渲染，或只重渲缺失镜。",
        [
            {"id": "rerender_missing", "label": "重渲缺失镜"},
            {"id": "rerender_all", "label": "完整重渲"},
        ],
    ),
    (
        "llm_json",
        re.compile(
            r"LLM JSON|Expecting value|Expecting ['\"],|未返回合法 JSON|JSON 解析失败",
            re.I,
        ),
        "AI 返回格式损坏",
        "模型输出不是合法 JSON（常被截断或夹杂说明文字）。换模型或重试通常可恢复。",
        [
            {"id": "retry", "label": "重试成刊/起草"},
            {"id": "switch_model", "label": "切换模型"},
        ],
    ),
    (
        "generate_failed",
        re.compile(r"generate_failed", re.I),
        "分镜生成失败",
        "脚本/分镜 LLM 调用失败。可换模型后重试，或先改主题再生成。",
        [
            {"id": "retry", "label": "重试生成"},
            {"id": "switch_model", "label": "切换模型"},
        ],
    ),
    (
        "docker_unavailable",
        re.compile(r"Docker 不可用|docker.*(not|不可)|unavailable", re.I),
        "沙箱 Docker 不可用",
        "本机 Docker 未启动或无权访问，demo 验证无法执行。",
        [
            {"id": "retry_verify", "label": "启动后重试验证"},
        ],
    ),
    (
        "agnes_no_url",
        re.compile(r"completed but no url|Agnes video completed but no url", re.I),
        "Agnes 成片无下载地址",
        "任务已完成但未返回 video url，多为上游短暂故障。",
        [{"id": "retry", "label": "重试本镜"}],
    ),
]


def _short_detail(msg: str, n: int = 160) -> str:
    s = re.sub(r"\s+", " ", (msg or "").strip())
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def classify_error(message: Any, *, fallback_title: str = "操作失败") -> dict[str, Any]:
    """Return a structured actionable error for UI rendering."""
    raw = str(message or "").strip()
    detail = _short_detail(raw)
    for code, pat, title, reason, actions in _RULES:
        if pat.search(raw):
            # Prefer more specific network reason when edge-tts + network tokens.
            if code == "edge_tts_network" and not any(
                x in raw
                for x in (
                    "nodename",
                    "Cannot connect",
                    "gaierror",
                    "Timeout",
                    "NoAudioReceived",
                    "连不上",
                )
            ):
                reason = "edge-tts 命令失败。可改用内置 API，或检查 CLI 是否装在当前环境。"
            return {
                "code": code,
                "title": title,
                "reason": reason,
                "detail": detail,
                "actions": [dict(a) for a in actions],
                "raw": raw[:400],
            }
    return {
        "code": "generic",
        "title": fallback_title,
        "reason": detail or "未知错误",
        "detail": detail,
        "actions": [{"id": "retry", "label": "重试"}],
        "raw": raw[:400],
    }


def attach_action(payload: dict[str, Any], message: Any, *, key: str = "action_error") -> dict[str, Any]:
    """Mutate/return payload with an ``action_error`` field derived from message."""
    out = dict(payload or {})
    out[key] = classify_error(message)
    return out


JOURNAL_CHECK_LABELS: dict[str, str] = {
    "cards_ge_5": "卡片数达标",
    "kinds_ge_3": "类型多样",
    "has_front_matter": "导读/目录齐全",
    "evidence_coverage_ge_half": "证据覆盖 ≥ 半",
    "no_theme_pad": "无模板注水",
    "flow_not_truncated": "流程未截断",
    "diagrams_complete": "图示齐全",
    "cover_tags_ok": "封面标签完整",
    "market_note_clean": "市场注干净",
    "data_has_metric": "数据卡有指标",
    "compare_has_sides": "对比卡双边齐全",
    "no_shallow_cliche": "无空洞套话",
    "mode_not_cached": "非缓存降级",
}

PRES_CONTENT_LABELS: dict[str, str] = {
    "depth_ok": "文稿深度达标",
    "stage_built": "舞台已构建",
    "a1_confirmed": "已确认 A1",
    "demo_verify_pass": "沙箱验证通过",
    "narration_timeline_ok": "旁白时间轴 OK",
}


def journal_quality_items(depth: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten ``journal_depth_report`` into panel items."""
    d = depth if isinstance(depth, dict) else {}
    checks = d.get("checks") if isinstance(d.get("checks"), dict) else {}
    stats = d.get("stats") if isinstance(d.get("stats"), dict) else {}
    items: list[dict[str, Any]] = []
    for key, label in JOURNAL_CHECK_LABELS.items():
        if key not in checks:
            continue
        ok = bool(checks[key])
        detail = ""
        if key == "cards_ge_5":
            detail = f"{stats.get('cards', 0)} 张"
        elif key == "kinds_ge_3":
            kinds = stats.get("kinds") or []
            detail = f"{len(kinds)} 种" + (f"（{', '.join(kinds[:4])}）" if kinds else "")
        elif key == "evidence_coverage_ge_half":
            detail = f"{stats.get('with_evidence', 0)}/{stats.get('cards', 0)}"
        elif key == "flow_not_truncated" and stats.get("flow_broken"):
            detail = f"{stats.get('flow_broken')} 处截断"
        elif key == "has_front_matter":
            detail = f"导读 {stats.get('promises', 0)} · 目录 {stats.get('toc', 0)}"
        items.append(
            {
                "id": key,
                "label": label,
                "status": "pass" if ok else "fail",
                "detail": detail,
            }
        )
    return items


def presentation_quality_items(
    content_qc: Optional[dict[str, Any]] = None,
    *,
    final_qc: Optional[dict[str, Any]] = None,
    verification: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Flatten dual QC + verification into panel items."""
    items: list[dict[str, Any]] = []
    cq = content_qc if isinstance(content_qc, dict) else {}
    checks = cq.get("checks") if isinstance(cq.get("checks"), dict) else {}
    for key, label in PRES_CONTENT_LABELS.items():
        if key not in checks:
            continue
        items.append(
            {
                "id": key,
                "label": label,
                "status": "pass" if checks[key] else "fail",
                "detail": "",
            }
        )
    v = verification if isinstance(verification, dict) else (cq.get("verification") or {})
    if isinstance(v, dict) and (v.get("declared") or v.get("roles_present")):
        if v.get("ok"):
            st, detail = "pass", f"{v.get('passed', 0)}/{v.get('declared', 0)} 步"
        elif v.get("pending"):
            st, detail = "pending", f"{v.get('pending')} 步未跑"
        elif v.get("unavailable"):
            st, detail = "fail", "Docker 不可用"
        elif v.get("failed"):
            st, detail = "fail", f"{v.get('failed')} 步失败"
        elif v.get("missing_roles"):
            st, detail = "fail", "缺声明：" + "、".join(v.get("missing_roles") or [])
        else:
            st, detail = "pending", "未声明 / 未跑"
        # Prefer dedicated verify row; avoid duplicate if demo_verify_pass already listed
        if not any(i["id"] == "demo_verify_pass" for i in items):
            items.append(
                {"id": "sandbox_verify", "label": "沙箱验证", "status": st, "detail": detail}
            )
        else:
            for i in items:
                if i["id"] == "demo_verify_pass" and detail:
                    i["detail"] = detail
    fq = final_qc if isinstance(final_qc, dict) else {}
    if fq:
        if not fq.get("path"):
            items.append(
                {
                    "id": "final_imported",
                    "label": "成片已导入",
                    "status": "pending",
                    "detail": "尚未导入",
                }
            )
        else:
            items.append(
                {
                    "id": "final_qc",
                    "label": "成片质检",
                    "status": "pass" if fq.get("ok") else "fail",
                    "detail": "；".join((fq.get("reasons") or [])[:2]),
                }
            )
    return items
