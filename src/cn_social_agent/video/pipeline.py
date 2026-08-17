"""Script generation + local render pipeline (edge-tts + Pillow + ffmpeg)."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import wave
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

FUNNEL_KEYS = (
    "t_created",
    "t_script_ready",
    "t_l0_ready",
    "t_l1_ready",
    "t_downloaded",
)

# Mid-render progress mirrored into wbmeta so /status survives refresh.
RENDER_PROGRESS_KEYS = (
    "render_progress",
    "render_message",
    "render_scene_i",
    "render_scene_n",
    "render_started_at",
)


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def apply_funnel_stamps(script: str, *keys: str) -> str:
    """Set funnel timestamp keys once (skip if already present)."""
    plain, meta = decode_script_bundle(script or "")
    now = utc_now_iso()
    changed = False
    for key in keys:
        if key not in FUNNEL_KEYS:
            continue
        if meta.get(key):
            continue
        meta[key] = now
        changed = True
    if not changed and script:
        return script
    meta["full_script"] = plain
    return encode_script_bundle(meta)


def funnel_snapshot(project: dict[str, Any]) -> dict[str, Any]:
    """Extract funnel timestamps from wbmeta (with created_at fallback)."""
    _plain, meta = decode_script_bundle(project.get("script") or "")
    out: dict[str, Any] = {k: (meta.get(k) or None) for k in FUNNEL_KEYS}
    if not out["t_created"]:
        out["t_created"] = project.get("created_at") or None
    return out


def clear_render_progress(script: str) -> str:
    """Drop mid-render progress keys from wbmeta (keep body + other meta)."""
    plain, meta = decode_script_bundle(script or "")
    changed = False
    for key in RENDER_PROGRESS_KEYS:
        if key in meta:
            meta.pop(key, None)
            changed = True
    if not changed:
        return script or ""
    meta["full_script"] = plain
    return encode_script_bundle(meta)


def apply_render_progress(
    script: str,
    *,
    progress: int,
    message: str,
    scene_i: int | None = None,
    scene_n: int | None = None,
    started_at: str | None = None,
) -> str:
    """Write durable render progress into wbmeta."""
    updates: dict[str, Any] = {
        "render_progress": max(0, min(100, int(progress))),
        "render_message": (message or "")[:240],
    }
    if scene_i is not None:
        updates["render_scene_i"] = int(scene_i)
    if scene_n is not None:
        updates["render_scene_n"] = int(scene_n)
    if started_at:
        updates["render_started_at"] = started_at
    elif not decode_script_bundle(script or "")[1].get("render_started_at"):
        updates["render_started_at"] = utc_now_iso()
    return merge_script_meta(script or "", **updates)


def job_from_wbmeta(
    project: dict[str, Any],
    delivery: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Rebuild an in-flight job dict from wbmeta when memory job is gone."""
    status = str(project.get("status") or "")
    if status != "rendering":
        return None
    _plain, meta = decode_script_bundle(project.get("script") or "")
    if meta.get("render_progress") is None and not meta.get("render_message"):
        return None
    delivery = delivery or {}
    try:
        progress = int(meta.get("render_progress") or 0)
    except (TypeError, ValueError):
        progress = 0
    scene_i = meta.get("render_scene_i")
    scene_n = meta.get("render_scene_n")
    try:
        scene_i = int(scene_i) if scene_i is not None else None
    except (TypeError, ValueError):
        scene_i = None
    try:
        scene_n = int(scene_n) if scene_n is not None else None
    except (TypeError, ValueError):
        scene_n = None
    return {
        "status": "rendering",
        "progress": max(0, min(100, progress)),
        "message": str(meta.get("render_message") or "渲染中…"),
        "scene_i": scene_i,
        "scene_n": scene_n,
        "delivery_level": meta.get("delivery_level") or delivery.get("delivery_level"),
        "render_mode": meta.get("render_mode") or delivery.get("render_mode"),
        "from_wbmeta": True,
    }

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[3]
VIDEO_ROOT = Path(os.getenv("VIDEO_DATA_DIR", str(PROJECT_ROOT / "data" / "videos")))

GENERATE_PROMPT = """你是面向程序员/科技受众的竖屏口播编导。目标是做出「看完有收获」的中长口播，不是口号卡片。
可对标财经深度分析片的叙事密度：悬念标题 → 论点 → 证据 → 规律 → 清晰结论/行动。

只输出 JSON，不要 markdown：
{{
  "title": "作品标题（≤22字；深度分析角度用「标的+悬念+反转结论」公式）",
  "cover_hook": "封面大字（≤14字，停滑）",
  "full_script": "完整口播串联稿（必须足够长，能撑满目标时长）",
  "hashtags": ["话题1", "话题2", "话题3"],
  "cta": "结尾行动号召",
  "audience": "目标受众一句话",
  "scene_setting": "具体场景",
  "platform": "主投放平台",
  "scenes": [
    {{
      "num": 1,
      "role": "hook|pain|context|thesis|evidence|pattern|verdict|value|steps|proof|compare|pitfall|cta 之一",
      "narration": "本镜口播：口语、信息密度高，禁止空话；本镜建议 {sec_per_scene} 秒左右的说话量（约 {chars_per_scene} 字）",
      "on_screen": "画面主字幕（≤18字，每镜不同；必须是本镜口播的核心信息词，禁止空口号）",
      "visual": "本镜画面说明，两段用｜分隔：①板式（大数字/数据条/清单/对比双栏等，给草稿卡）②镜头（主体+场景+运镜，给成片，如「俯拍桌面显示器上的折线图，缓慢推进」）",
      "mood": "情绪词",
      "takeaway": "本镜观众记住的一点（可空）"
    }}
  ]
}}

硬性要求：
1) 总口播时长约 {seconds} 秒（允许 ±15%）。口播总字数大约 {min_chars}-{max_chars} 字（中文约 4–4.5 字/秒）。
2) 分镜数量 {min_scenes}-{max_scenes} 个；每镜 on_screen / visual 不得重复。
3) 结构按内容角度走（见下）；禁止「很好用」「很强大」空形容词堆砌；必须有可执行结论。
4) 画面必须贴合本镜口播：on_screen 从 narration 提炼；visual 禁止空泛「科技感背景」；每镜主体要能听出口播在讲什么。
5) visual 必须按 role 换板式，且含镜头描述（｜后半段）。
6) **一镜一个节拍**：每镜旁白只讲 1 个要点（1–2 句）；多要点必须拆成多镜，禁止一镜堆清单。

内容角度：{content_angle}
主题：{topic}
语气：{tone}
受众：{audience}
场景：{scene_setting}
平台：{platform}
行动号召：{cta}
补充卖点：{brief}
"""

CONTENT_ANGLES: dict[str, dict[str, Any]] = {
    "intro": {
        "label": "入门上手",
        "default_seconds": 120,
        "default_bg": "night",
        "hint": "从零跑通：是什么→环境→三步安装→验证→常见坑→下一步",
        "structure": "hook→pain→context→steps×3→proof→pitfall→cta",
    },
    "idea": {
        "label": "核心思想",
        "default_seconds": 90,
        "default_bg": "dawn",
        "hint": "一个观念说透：为何火→核心模型→解决什么→误区→记住一句",
        "structure": "hook→pain→thesis→value→pitfall→cta",
    },
    "compare": {
        "label": "横向对比",
        "default_seconds": 120,
        "default_bg": "studio",
        "hint": "点名 2 个替代方案：维度对比→适合谁→不适合谁→选型结论",
        "structure": "hook→pain→compare→evidence→verdict→cta",
    },
    "deep_analysis": {
        "label": "深度分析",
        "default_seconds": 180,
        "default_bg": "desk",
        "hint": (
            "对标财经深度片：悬念标题→现象/痛点→核心论点(thesis)→"
            "2–3条证据(evidence)→规律/模式(pattern)→清晰结论与行动点(verdict)→避坑→CTA。"
            "标题公式：标的+惊人规律？+未完待续的悬念+但结论已清晰。"
        ),
        "structure": "hook→pain→thesis→evidence×2→pattern→verdict→pitfall→cta",
    },
    "general": {
        "label": "深度口播",
        "default_seconds": 120,
        "default_bg": "night",
        "hint": "钩子→痛点→干货展开→证据→坑→行动",
        "structure": "hook→pain→context→value/steps→proof→pitfall→cta",
    },
}

# Phase C vertical templates (开箱可复制). UI / Agent pick by id.
VIDEO_TEMPLATES: dict[str, dict[str, Any]] = {
    "product_update": {
        "id": "product_update",
        "label": "产品更新",
        "hint": "停滑条：这周上了什么 → 谁该关心 → 3 变化 → 怎么试",
        "content_angle": "intro",
        "target_seconds": 15,
        "bg_theme": "studio",
        "motion": "kenburns",
        "roles": ["hook", "value", "steps", "cta"],
        "placeholder_topic": "本周产品更新：…",
    },
    "tech_rant": {
        "id": "tech_rant",
        "label": "技术吐槽 / 观点",
        "hint": "15s 观点：行业信号 → 判断一句 → 误区 → CTA",
        "content_angle": "idea",
        "target_seconds": 15,
        "bg_theme": "dawn",
        "motion": "kenburns",
        "roles": ["hook", "pain", "thesis", "cta"],
        "placeholder_topic": "吐槽 / 观点：…",
    },
    "tutorial": {
        "id": "tutorial",
        "label": "教程口播",
        "hint": "入门教程：是什么 → 三步上手 → 一个坑（约 60–90s）",
        "content_angle": "intro",
        "target_seconds": 90,
        "bg_theme": "night",
        "motion": "kenburns",
        "roles": ["hook", "pain", "context", "steps", "pitfall", "cta"],
        "placeholder_topic": "教程：从零跑通 …",
    },
}

DEFAULT_TEMPLATE_ID = "product_update"


def get_video_template(template_id: str | None) -> dict[str, Any]:
    from cn_social_agent.packs.loader import effective_templates, pack_video_defaults

    catalog = effective_templates(VIDEO_TEMPLATES)
    defaults = pack_video_defaults()
    fallback = (
        str(defaults.get("default_template_id") or "").strip()
        or DEFAULT_TEMPLATE_ID
    )
    tid = (template_id or "").strip() or fallback
    return dict(catalog.get(tid) or catalog.get(fallback) or VIDEO_TEMPLATES[DEFAULT_TEMPLATE_ID])


def apply_template_defaults(
    *,
    template_id: str | None = None,
    target_seconds: int | None = None,
    content_angle: str | None = None,
    bg_theme: str | None = None,
    motion: str | None = None,
) -> dict[str, Any]:
    """Merge template defaults with explicit overrides for create/generate."""
    from cn_social_agent.packs.loader import pack_video_defaults

    tmpl = get_video_template(template_id)
    pack_defaults = pack_video_defaults()
    angle = (content_angle or tmpl["content_angle"] or "intro").strip()
    if angle not in CONTENT_ANGLES:
        angle = "intro"
    if target_seconds is not None:
        seconds = int(target_seconds)
    elif tmpl.get("target_seconds") is not None:
        seconds = int(tmpl["target_seconds"])
    elif pack_defaults.get("target_seconds") is not None:
        seconds = int(pack_defaults["target_seconds"])
    else:
        seconds = 15
    seconds = max(15, min(180, seconds))
    bg = (
        bg_theme
        or tmpl.get("bg_theme")
        or pack_defaults.get("bg_theme")
        or CONTENT_ANGLES[angle].get("default_bg")
        or "night"
    )
    if bg not in BG_THEMES:
        bg = "night"
    mot = (motion or tmpl.get("motion") or "kenburns").strip()
    if mot not in MOTIONS:
        mot = "kenburns"
    return {
        "template_id": tmpl["id"],
        "content_angle": angle,
        "target_seconds": seconds,
        "bg_theme": bg,
        "motion": mot,
        "roles": list(tmpl.get("roles") or []),
        "label": tmpl.get("label") or tmpl["id"],
        "hint": tmpl.get("hint") or "",
    }


ROLE_LABELS = {
    "hook": "钩子",
    "pain": "痛点",
    "context": "背景",
    "thesis": "论点",
    "evidence": "证据",
    "pattern": "规律",
    "verdict": "结论",
    "value": "干货",
    "steps": "步骤",
    "proof": "实证",
    "compare": "对比",
    "pitfall": "避坑",
    "cta": "行动",
}

ROLE_COLORS = {
    "hook": ((255, 90, 70), (40, 12, 18)),
    "pain": ((255, 170, 60), (36, 24, 10)),
    "context": ((160, 140, 255), (20, 16, 36)),
    "thesis": ((255, 200, 80), (36, 28, 8)),
    "evidence": ((80, 200, 255), (8, 24, 36)),
    "pattern": ((255, 120, 80), (36, 16, 10)),
    "verdict": ((80, 220, 140), (10, 32, 20)),
    "value": ((64, 200, 180), (10, 28, 32)),
    "steps": ((80, 200, 120), (10, 28, 18)),
    "proof": ((120, 160, 255), (12, 18, 40)),
    "compare": ((255, 140, 100), (36, 18, 12)),
    "pitfall": ((255, 100, 120), (36, 12, 18)),
    "cta": ((255, 210, 80), (36, 28, 8)),
}

# Background themes: (accent_boost, base_rgb, pattern)
BG_THEMES: dict[str, dict[str, Any]] = {
    "night": {"base": (12, 16, 32), "pattern": "stars", "label": "深夜蓝"},
    "dawn": {"base": (42, 28, 48), "pattern": "wash", "label": "晨曦紫"},
    "studio": {"base": (24, 24, 28), "pattern": "grid", "label": "影棚灰"},
    "neon": {"base": (8, 20, 28), "pattern": "neon", "label": "霓虹"},
    "paper": {"base": (244, 240, 232), "pattern": "paper", "label": "纸感浅底", "ink": (28, 24, 20)},
    "forest": {"base": (14, 32, 24), "pattern": "leaves", "label": "森系绿"},
    "desk": {"base": (10, 14, 18), "pattern": "candles", "label": "分析台（深度分析）"},
}

# Local still→video camera presets. zoom_end must be clearly >1 so motion reads on phone.
# pan: center | up | down | left | right | diag
MOTIONS = {
    "kenburns": {
        "label": "自动分镜运镜",
        "zoom_start": 1.0,
        "zoom_end": 1.48,
        "pan": "up",
    },
    "punch_in": {
        "label": "开场快推",
        "zoom_start": 1.0,
        "zoom_end": 1.72,
        "pan": "center",
    },
    "drift": {
        "label": "横向滑移",
        "zoom_start": 1.22,
        "zoom_end": 1.38,
        "pan": "right",
    },
    "pull_back": {
        "label": "拉远揭示",
        "zoom_start": 1.55,
        "zoom_end": 1.08,
        "pan": "center",
    },
    "diagonal": {
        "label": "对角推进",
        "zoom_start": 1.05,
        "zoom_end": 1.55,
        "pan": "diag",
    },
    "static": {
        "label": "静止",
        "zoom_start": 1.0,
        "zoom_end": 1.0,
        "pan": "center",
    },
}

_ROLE_MOTION = {
    "hook": "punch_in",
    "pain": "diagonal",
    "context": "kenburns",
    "thesis": "punch_in",
    "evidence": "drift",
    "pattern": "diagonal",
    "verdict": "pull_back",
    "value": "drift",
    "steps": "drift",
    "proof": "kenburns",
    "compare": "diagonal",
    "pitfall": "punch_in",
    "cta": "pull_back",
}


def duration_plan(seconds: int) -> dict[str, int]:
    """Scene/char budget so TTS can actually fill 1–3 minute videos."""
    sec = max(15, min(180, int(seconds or 120)))
    # ~4.5 Chinese chars/sec for clear口播; TTS often lands near this
    total_chars = int(sec * 4.5)
    if sec <= 45:
        n = 6
    elif sec <= 90:
        n = 9
    elif sec <= 120:
        n = 11
    else:
        n = 14
    per = max(36, total_chars // n)
    return {
        "seconds": sec,
        "min_scenes": max(5, n - 2),
        "max_scenes": n + 2,
        "min_chars": int(total_chars * 0.9),
        "max_chars": int(total_chars * 1.2),
        "sec_per_scene": max(5, sec // n),
        "chars_per_scene": per,
    }


def list_video_styles() -> dict[str, Any]:
    from cn_social_agent.packs.loader import (
        effective_templates,
        get_active_pack,
        pack_video_defaults,
    )
    from cn_social_agent.video.agnes_client import AgnesVideoClient

    catalog = effective_templates(VIDEO_TEMPLATES)
    defaults = pack_video_defaults()
    default_tid = (
        str(defaults.get("default_template_id") or "").strip() or DEFAULT_TEMPLATE_ID
    )
    default_seconds = int(defaults.get("target_seconds") or 15)
    pack = get_active_pack()
    return {
        "durations": [15, 30, 45, 60, 90, 120, 180],
        "default_seconds": max(15, min(180, default_seconds)),
        "default_template_id": default_tid if default_tid in catalog else DEFAULT_TEMPLATE_ID,
        "pack": pack.to_dict() if pack else None,
        "templates": [
            {
                "id": t["id"],
                "label": t.get("label") or t["id"],
                "hint": t.get("hint") or "",
                "content_angle": t.get("content_angle"),
                "target_seconds": t.get("target_seconds"),
                "bg_theme": t.get("bg_theme"),
                "roles": list(t.get("roles") or []),
                "placeholder_topic": t.get("placeholder_topic") or "",
            }
            for t in catalog.values()
        ],
        "content_angles": [
            {
                "id": k,
                "label": v.get("label") or k,
                "default_seconds": v.get("default_seconds"),
                "hint": v.get("hint"),
            }
            for k, v in CONTENT_ANGLES.items()
        ],
        "bg_themes": [
            {"id": k, "label": v.get("label") or k} for k, v in BG_THEMES.items()
        ],
        "motions": [
            {"id": k, "label": v.get("label") or k} for k, v in MOTIONS.items()
        ],
        "render_modes": [
            {
                "id": "local",
                "label": "L0 分镜草稿（本地卡片）",
                "delivery_level": "l0",
                "configured": True,
            },
            {
                "id": "agnes-video",
                "label": "L1 成片（Agnes Video v2.0）",
                "delivery_level": "l1",
                "configured": AgnesVideoClient.configured(),
            },
        ],
        "delivery_levels": [
            {"id": "l0", "label": "分镜草稿", "render_mode": "local"},
            {"id": "l1", "label": "成片", "render_mode": "agnes-video"},
        ],
        "roles": list(ROLE_LABELS.keys()),
    }


def pack_scene_meta(meta: dict[str, Any]) -> str:
    return json.dumps(
        {
            "role": meta.get("role") or "value",
            "on_screen": meta.get("on_screen") or "",
            "visual": meta.get("visual") or "",
            "mood": meta.get("mood") or "",
            "poster_path": meta.get("poster_path") or "",
            "scene_render_mode": meta.get("scene_render_mode") or "",
        },
        ensure_ascii=False,
    )


def unpack_scene_meta(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return {
                    "role": (data.get("role") or "value").lower(),
                    "on_screen": (data.get("on_screen") or "").strip(),
                    "visual": (data.get("visual") or "").strip(),
                    "mood": (data.get("mood") or "").strip(),
                    "poster_path": (data.get("poster_path") or "").strip(),
                    "scene_render_mode": (data.get("scene_render_mode") or "").strip(),
                }
        except Exception:  # noqa: BLE001
            pass
    # Legacy: plain poster path after old renders wiped JSON
    if text.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return {
            "role": "value",
            "on_screen": "",
            "visual": "",
            "mood": "",
            "poster_path": text,
            "scene_render_mode": "",
        }
    return {
        "role": "value",
        "on_screen": text[:40],
        "visual": text,
        "mood": "",
        "poster_path": "",
        "scene_render_mode": "",
    }


def scene_meta_for_persist(meta: dict[str, Any], *, poster: Path | str = "") -> str:
    """Keep editable meta when writing poster path after render."""
    merged = {
        **meta,
        "poster_path": str(poster or meta.get("poster_path") or ""),
    }
    return pack_scene_meta(merged)


def project_dir(project_id: str) -> Path:
    d = VIDEO_ROOT / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty LLM output")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # Try direct parse, then first {...} block, then repair common issues.
    candidates = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    # Fix trailing commas
    for c in list(candidates):
        candidates.append(re.sub(r",\s*([}\]])", r"\1", c))
    last_err: Exception | None = None
    for c in candidates:
        try:
            data = json.loads(c)
            if isinstance(data, dict):
                return data
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
    raise ValueError(f"invalid JSON from LLM: {last_err}")


def _fallback_from_topic(
    topic: str,
    seconds: int = 120,
    *,
    audience: str = "",
    scene_setting: str = "",
    cta: str = "",
    content_angle: str = "general",
) -> dict[str, Any]:
    """Deterministic denser scenes when LLM JSON fails — sized to duration_plan."""
    plan = duration_plan(seconds)
    who = audience or "独立开发者"
    scene = scene_setting or f"刷到「{topic}」却不知道值不值得学"
    action = cta or "评论你最卡的一步，我回清单"
    angle = content_angle if content_angle in CONTENT_ANGLES else "general"

    def pad(text: str) -> str:
        need = plan["chars_per_scene"]
        if len(text) >= need:
            return text
        filler = (
            f"具体来说，围绕「{topic}」你要先搞清楚问题定义，再动手。"
            f"别急着堆名词，先抓住可验证的一点，再谈扩展。"
        )
        out = text
        while len(out) < need:
            out += filler
        return out[: need + 20]

    if angle == "deep_analysis":
        hooks = [
            {
                "role": "hook",
                "narration": pad(
                    f"别划走。关于「{topic}」，外面吵的是情绪，接下来{plan['seconds']}秒讲清规律和结论。"
                ),
                "on_screen": "情绪很多｜规律很少",
                "visual": "大数字悬念+反转预告",
                "mood": "抓人",
            },
            {
                "role": "pain",
                "narration": pad(f"如果你是{who}，卡在：{scene}。信息爆炸，却没有一条能指导行动。"),
                "on_screen": "看了很多，仍不会下决定",
                "visual": "痛点引用卡",
                "mood": "共鸣",
            },
            {
                "role": "thesis",
                "narration": pad(
                    f"核心论点先说清：围绕「{topic}」，真正该盯的不是热闹，而是可验证的关键变量。"
                ),
                "on_screen": "论点：盯关键变量",
                "visual": "论点大字条",
                "mood": "立论",
            },
            {
                "role": "evidence",
                "narration": pad("证据一：看增长/活跃/交付这类硬指标，而不是口号。把数字和现象对齐。"),
                "on_screen": "证据① 硬指标",
                "visual": "数据条+关键数字",
                "mood": "冷静",
            },
            {
                "role": "evidence",
                "narration": pad("证据二：对照历史同类情况，找重复出现的结构，而不是单次新闻。"),
                "on_screen": "证据② 历史对照",
                "visual": "时间轴对照",
                "mood": "冷静",
            },
            {
                "role": "pattern",
                "narration": pad("规律是：热闹先行，兑现滞后；等情绪退去，关键变量才会露出买点/行动点。"),
                "on_screen": "规律：热闹≠兑现",
                "visual": "趋势折线+标注",
                "mood": "顿悟",
            },
            {
                "role": "verdict",
                "narration": pad(
                    f"结论已经清晰：对「{topic}」，先验证最小闭环再加仓学习成本；行动点写进笔记。"
                ),
                "on_screen": "结论：先验证再加码",
                "visual": "绿色结论条+行动点",
                "mood": "清晰",
            },
            {
                "role": "pitfall",
                "narration": pad("避坑：别用标题党当论据，也别在没有验证指标时跟风 All-in。"),
                "on_screen": "避坑：别用情绪下单",
                "visual": "警告条",
                "mood": "警惕",
            },
            {
                "role": "cta",
                "narration": pad(f"有用就收藏。{action}。下期继续拆下一组证据。"),
                "on_screen": action[:18],
                "visual": "行动按钮卡",
                "mood": "行动",
            },
        ]
        title = (topic[:14] + "｜规律与结论") if topic else "深度分析"
        cover = "规律已现｜结论清晰"
        tags = ["深度分析", "程序员", "决策"]
    else:
        hooks = [
            {
                "role": "hook",
                "narration": pad(f"别划走。接下来用大约{plan['seconds']}秒，把「{topic}」讲到你能动手。"),
                "on_screen": "别划走｜能动手的干货",
                "visual": "大数字倒计时+反常识标题",
                "mood": "抓人",
            },
            {
                "role": "pain",
                "narration": pad(f"如果你是{who}，是不是也卡在：{scene}？信息很多，却没有一条能落地。"),
                "on_screen": "信息很多，落地很少",
                "visual": "痛点引用卡",
                "mood": "共鸣",
            },
            {
                "role": "context",
                "narration": pad(f"先一句话：{topic}到底解决什么。别被营销词带走，抓住它的边界。"),
                "on_screen": "一句话它是什么",
                "visual": "定义卡+关键词",
                "mood": "清晰",
            },
            {
                "role": "value",
                "narration": pad("结论先行：先跑最小可用，再谈扩展。今天只做一个闭环。"),
                "on_screen": "结论：先闭环",
                "visual": "结论大字卡",
                "mood": "利落",
            },
            {
                "role": "steps",
                "narration": pad("第一步：准备环境与依赖，确认版本，避免隐式坑。"),
                "on_screen": "步骤1 · 环境",
                "visual": "步骤清单 1/3",
                "mood": "可执行",
            },
            {
                "role": "steps",
                "narration": pad("第二步：按官方最小示例跑通 Hello World，截图留证。"),
                "on_screen": "步骤2 · 跑通",
                "visual": "步骤清单 2/3",
                "mood": "可执行",
            },
            {
                "role": "steps",
                "narration": pad("第三步：换成你自己的输入，验证输出符合预期，再写进笔记。"),
                "on_screen": "步骤3 · 换成你的",
                "visual": "步骤清单 3/3",
                "mood": "可执行",
            },
            {
                "role": "proof",
                "narration": pad("这样做的前后差：以前收藏十篇用不上，现在有一条可复现路径。"),
                "on_screen": "前后对比",
                "visual": "双栏前后对比",
                "mood": "可信",
            },
            {
                "role": "compare",
                "narration": pad("和常见替代方案比：它更适合个人闭环；别的可能更适合团队或 IDE 内编码。"),
                "on_screen": "和替代方案差在哪",
                "visual": "对比双栏",
                "mood": "清醒",
            },
            {
                "role": "pitfall",
                "narration": pad("最常见坑：一上来堆全功能。先最小闭环，再加自动化。"),
                "on_screen": "避坑：别一上来全功能",
                "visual": "警告条避坑卡",
                "mood": "警惕",
            },
            {
                "role": "cta",
                "narration": pad(f"有用就收藏。{action}。下期继续拆进阶玩法。"),
                "on_screen": action[:18],
                "visual": "大按钮行动卡",
                "mood": "行动",
            },
        ]
        title = (topic[:16] + "｜能动手版") if topic else "深度短视频"
        cover = topic[:12] or "别划走"
        tags = ["开源", "程序员", "实操"]

    n = min(len(hooks), plan["max_scenes"])
    n = max(plan["min_scenes"], n) if len(hooks) >= plan["min_scenes"] else len(hooks)
    scenes = []
    for i, row in enumerate(hooks[:n], start=1):
        scenes.append({"num": i, **row})
    return {
        "title": title,
        "cover_hook": cover,
        "full_script": "\n".join(s["narration"] for s in scenes),
        "hashtags": tags,
        "cta": action,
        "audience": who,
        "scene_setting": scene,
        "platform": "抖音",
        "scenes": scenes,
        "content_angle": angle,
    }


async def generate_script(
    llm: Any,
    *,
    topic: str,
    tone: str = "活泼口播",
    seconds: int = 120,
    model: str = "",
    audience: str = "",
    scene_setting: str = "",
    platform: str = "",
    cta: str = "",
    brief: str = "",
    bg_theme: str = "night",
    motion: str = "kenburns",
    render_mode: str = "local",
    content_angle: str = "general",
) -> dict[str, Any]:
    plan = duration_plan(seconds)
    seconds = plan["seconds"]
    motion = motion if motion in MOTIONS else "kenburns"
    render_mode = render_mode if render_mode in ("local", "agnes-video") else "local"
    content_angle = content_angle if content_angle in CONTENT_ANGLES else "general"
    angle = CONTENT_ANGLES[content_angle]
    if content_angle == "deep_analysis" and bg_theme == "night":
        bg_theme = str(angle.get("default_bg") or "desk")
    bg_theme = bg_theme if bg_theme in BG_THEMES else "night"
    prompt = GENERATE_PROMPT.format(
        topic=topic,
        tone=tone or "硬核但不装",
        seconds=seconds,
        sec_per_scene=plan["sec_per_scene"],
        chars_per_scene=plan["chars_per_scene"],
        min_chars=plan["min_chars"],
        max_chars=plan["max_chars"],
        min_scenes=plan["min_scenes"],
        max_scenes=plan["max_scenes"],
        content_angle=(
            f"{content_angle}（{angle.get('label')}：{angle.get('hint')}；"
            f"分镜结构：{angle.get('structure')}）"
        ),
        audience=audience or "独立开发者 / 程序员",
        scene_setting=scene_setting or "刷到热点却不知道值不值得投入学习",
        platform=platform or "抖音/视频号/B站",
        cta=cta or "收藏本集，评论你最卡的一步",
        brief=brief or "无",
    )
    prompt += (
        f"\n背景主题：{BG_THEMES[bg_theme].get('label', bg_theme)}；"
        f"镜头：{MOTIONS[motion].get('label', motion)}；"
        f"引擎：{'Agnes文生视频' if render_mode == 'agnes-video' else '本地差异化卡片'}。"
        f"务必把 full_script 写满，scenes 合计口播接近 {seconds} 秒。"
        f"每镜 visual 板式必须不同。"
    )
    if content_angle == "deep_analysis":
        prompt += (
            "深度分析硬性：必须含 thesis、至少两镜 evidence、pattern、verdict；"
            "标题要有悬念+反转结论；每条证据要像可核对的事实，不要空话。"
        )
    # Cap tokens — very high caps slow/timeout Agnes and still need fallback
    max_tokens = 2800 if seconds <= 90 else (3600 if seconds <= 120 else 4200)
    data: dict[str, Any]
    llm_note = ""
    try:
        raw = await llm.chat_completion(
            [{"role": "user", "content": prompt}],
            model=model,
            temperature=0.45,
            max_tokens=max_tokens,
        )
        choice = (raw.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        try:
            data = _extract_json(content)
        except Exception:
            try:
                repair = await llm.chat_completion(
                    [
                        {
                            "role": "user",
                            "content": (
                                "把下面内容改成严格 JSON。必须含 title, cover_hook, full_script, "
                                "hashtags, cta, audience, scene_setting, platform, scenes。"
                                "scenes 每项含 num, role, narration, on_screen, visual, mood。"
                                "只输出 JSON。\n\n" + content[:3500]
                            ),
                        }
                    ],
                    model=model,
                    temperature=0.1,
                    max_tokens=max_tokens,
                )
                repair_content = (
                    ((repair.get("choices") or [{}])[0].get("message") or {}).get("content")
                    or ""
                )
                data = _extract_json(repair_content)
            except Exception:
                data = _fallback_from_topic(
                    topic,
                    seconds,
                    audience=audience,
                    scene_setting=scene_setting,
                    cta=cta,
                    content_angle=content_angle,
                )
                llm_note = "llm_json_fallback"
    except Exception as llm_exc:  # noqa: BLE001
        # Network/API timeout must not hard-fail the workshop — denser local script
        data = _fallback_from_topic(
            topic,
            seconds,
            audience=audience,
            scene_setting=scene_setting,
            cta=cta,
            content_angle=content_angle,
        )
        name = type(llm_exc).__name__
        msg = str(llm_exc).strip() or "no message"
        llm_note = f"llm_unavailable:{name}:{msg[:120]}"

    scenes = data.get("scenes") or []
    if not scenes:
        data = _fallback_from_topic(
            topic,
            seconds,
            audience=audience,
            scene_setting=scene_setting,
            cta=cta,
            content_angle=content_angle,
        )
        scenes = data["scenes"]
        llm_note = llm_note or "empty_scenes_fallback"

    norm = []
    for i, s in enumerate(scenes, start=1):
        if not isinstance(s, dict):
            continue
        narr = (s.get("narration") or s.get("content") or "").strip()
        if not narr:
            continue
        role = (s.get("role") or "value").strip().lower()
        if role not in ROLE_LABELS:
            role = "value"
        on_screen = (s.get("on_screen") or "").strip()
        visual = (s.get("visual") or "").strip()
        # If LLM omitted on_screen, take first narration clause (not the whole visual board jargon)
        if not on_screen:
            first = re.split(r"[。！？；\n]", narr)[0].strip()
            on_screen = (first or visual.split("｜")[0] or visual)[:18]
        if not visual:
            visual = on_screen
        mood = (s.get("mood") or "").strip()
        visual = ensure_visual_board_shot(
            visual,
            role=role,
            on_screen=on_screen,
            title=topic,
            narration=narr,
        )
        norm.append(
            {
                "num": int(s.get("num") or i),
                "role": role,
                "narration": narr,
                "on_screen": on_screen[:24],
                "visual": visual,
                "mood": mood,
            }
        )
    if not norm:
        data = _fallback_from_topic(
            topic,
            seconds,
            audience=audience,
            scene_setting=scene_setting,
            cta=cta,
            content_angle=content_angle,
        )
        norm = data["scenes"]

    # Ensure at least hook + cta exist
    roles = {s.get("role") for s in norm}
    if "hook" not in roles and norm:
        norm[0]["role"] = "hook"
    if "cta" not in roles and norm:
        norm[-1]["role"] = "cta"
    if content_angle == "deep_analysis" and norm:
        if "thesis" not in roles and len(norm) > 2:
            norm[2]["role"] = "thesis"
        if "verdict" not in roles and len(norm) > 3:
            norm[-2]["role"] = "verdict"

    # One beat per scene (口播节拍 = 视觉 step)
    norm = split_scenes_one_beat(
        norm,
        max_chars_per_scene=plan["chars_per_scene"],
        max_scenes=min(plan["max_scenes"] + 4, 16),
    )

    # Densify if LLM under-wrote — pad with spoken tips, never meta instructions.
    total_chars = sum(len(s["narration"]) for s in norm)
    if total_chars < plan["min_chars"] and norm:
        need = plan["min_chars"] - total_chars
        per = max(8, need // len(norm))
        for s in norm:
            if not (s.get("on_screen") or "").strip():
                first = re.split(r"[。！？；\n]", s["narration"])[0].strip()
                s["on_screen"] = (first or topic)[:18]
            tip = _spoken_pad_clause(topic, s.get("role") or "value")
            extra = ""
            while len(extra) < per:
                extra += tip
            s["narration"] = (s["narration"].rstrip("。") + "。" + extra)[
                : plan["chars_per_scene"] + 40
            ]

    data["scenes"] = norm
    data["title"] = (data.get("title") or topic)[:40]
    data["cover_hook"] = (data.get("cover_hook") or data["title"])[:16]
    data["full_script"] = "\n".join(s["narration"] for s in data["scenes"])
    data["hashtags"] = data.get("hashtags") or []
    data["cta"] = data.get("cta") or cta or "关注我，下期继续"
    data["audience"] = data.get("audience") or audience
    data["scene_setting"] = data.get("scene_setting") or scene_setting
    data["platform"] = data.get("platform") or platform or "抖音"
    data["bg_theme"] = bg_theme
    data["motion"] = motion
    data["render_mode"] = render_mode
    data["content_angle"] = content_angle
    data["fail_reason"] = ""
    data["delivery_level"] = data.get("delivery_level") or ""
    data["storyboard_confirmed"] = False
    if llm_note:
        data["llm_note"] = llm_note
    return data


def split_scenes_one_beat(
    scenes: list[dict[str, Any]],
    *,
    max_chars_per_scene: int,
    max_scenes: int = 14,
) -> list[dict[str, Any]]:
    """Split multi-clause narrations so each scene carries ~one beat."""
    out: list[dict[str, Any]] = []

    for s in scenes:
        narr = (s.get("narration") or "").strip()
        clauses = [
            c.strip()
            for c in re.split(r"[。！？；\n]+", narr)
            if c.strip() and "这里补一句可执行细节" not in c
        ]
        # Multi-clause = multi-beat: always split (口播节拍 = 画面 step)
        if len(clauses) <= 1:
            row = dict(s)
            row["narration"] = narr
            out.append(row)
            continue

        base_role = (s.get("role") or "value").lower()
        base_visual = (s.get("visual") or "").strip()
        for i, clause in enumerate(clauses):
            if len(out) >= max_scenes:
                # Fold remainder into last scene
                if out:
                    tail = "。".join(clauses[i:])
                    out[-1]["narration"] = (
                        out[-1]["narration"].rstrip("。") + "。" + tail
                    )[: max_chars_per_scene + 40]
                break
            text = clause if clause.endswith(("。", "！", "？")) else clause + "。"
            if i == 0:
                role = base_role
                on_screen = (s.get("on_screen") or clause)[:24]
                visual = base_visual or f"{clause[:20]}｜close-up of the key point"
            else:
                role = "steps" if base_role in ("steps", "value", "proof") else base_role
                if role == "hook":
                    role = "value"
                on_screen = clause[:18]
                visual = f"{clause[:22]}｜vertical beat cut matching the tip"
            out.append(
                {
                    "num": len(out) + 1,
                    "role": role,
                    "narration": text,
                    "on_screen": on_screen[:24],
                    "visual": visual,
                    "mood": s.get("mood") or "",
                }
            )

    for i, row in enumerate(out, start=1):
        row["num"] = i
    # Keep hook/cta anchors
    if out:
        if out[0].get("role") != "hook":
            out[0]["role"] = "hook"
        if out[-1].get("role") != "cta":
            out[-1]["role"] = "cta"
    return out


def storyboard_outline(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compact outline for Checkpoint A1 (confirm before L0)."""
    rows: list[dict[str, Any]] = []
    for i, s in enumerate(scenes or [], start=1):
        meta = unpack_scene_meta(str(s.get("image_path") or ""))
        narr = (s.get("content") or s.get("narration") or "").strip()
        rows.append(
            {
                "scene_num": int(s.get("scene_num") or s.get("num") or i),
                "role": meta.get("role") or s.get("role") or "value",
                "on_screen": (meta.get("on_screen") or s.get("on_screen") or "")[:40],
                "visual": (meta.get("visual") or s.get("visual") or "")[:80],
                "narration_preview": narr[:60],
                "chars": len(narr),
            }
        )
    return rows


# Extra wbmeta keys for presentation track (and future extensions).
_PRESENTATION_META_KEYS = (
    "video_type",
    "aspect",
    "theme",
    "phase",
    "outline",
    "checkpoints",
    "presentation_path",
    "presentation_built",
    "dev_mode",
    "audio_ready",
    "publish",
    "content_pack",
    "thesis",
    "research_notes",
    "content_drafted",
)


def encode_script_bundle(data: dict[str, Any]) -> str:
    meta = {
        "cover_hook": data.get("cover_hook") or "",
        "hashtags": data.get("hashtags") or [],
        "cta": data.get("cta") or "",
        "audience": data.get("audience") or "",
        "scene_setting": data.get("scene_setting") or "",
        "platform": data.get("platform") or "",
        "bg_theme": data.get("bg_theme") or "night",
        "motion": data.get("motion") or "kenburns",
        "render_mode": data.get("render_mode") or "local",
        "content_angle": data.get("content_angle") or "general",
        "delivery_level": data.get("delivery_level") or "",
        "fail_reason": data.get("fail_reason") or "",
        "quality_gate_pass": data.get("quality_gate_pass"),
        "llm_note": data.get("llm_note") or "",
        "storyboard_confirmed": bool(data.get("storyboard_confirmed")),
        "template_id": data.get("template_id") or "",
        "target_seconds": data.get("target_seconds"),
        "output_storage_bucket": data.get("output_storage_bucket") or "",
        "output_storage_key": data.get("output_storage_key") or "",
    }
    for key in RENDER_PROGRESS_KEYS:
        if key in data and data.get(key) is not None and data.get(key) != "":
            meta[key] = data[key]
    for key in FUNNEL_KEYS:
        if data.get(key):
            meta[key] = data[key]
    for key in _PRESENTATION_META_KEYS:
        if key in data and data.get(key) is not None:
            meta[key] = data[key]
    body = data.get("full_script") or ""
    return "<!--wbmeta:" + json.dumps(meta, ensure_ascii=False) + "-->\n" + body


def decode_script_bundle(script: str) -> tuple[str, dict[str, Any]]:
    text = script or ""
    meta: dict[str, Any] = {}
    m = re.match(r"^<!--wbmeta:(.*?)-->\s*", text, flags=re.S)
    if m:
        try:
            meta = json.loads(m.group(1))
        except Exception:  # noqa: BLE001
            meta = {}
        text = text[m.end() :]
    return text, meta if isinstance(meta, dict) else {}


def merge_script_meta(script: str, **updates: Any) -> str:
    """Patch wbmeta fields while preserving plain script body."""
    plain, meta = decode_script_bundle(script or "")
    meta = {**meta, **{k: v for k, v in updates.items() if v is not None}}
    meta["full_script"] = plain
    return encode_script_bundle(meta)


def delivery_snapshot(project: dict[str, Any]) -> dict[str, Any]:
    """Derive L0/L1 delivery fields from project + wbmeta."""
    _plain, meta = decode_script_bundle(project.get("script") or "")
    render_mode = meta.get("render_mode") or "local"
    level = meta.get("delivery_level") or ""
    if not level and project.get("status") == "done":
        level = "l1" if render_mode == "agnes-video" else "l0"
    return {
        "render_mode": render_mode,
        "delivery_level": level or None,
        "fail_reason": meta.get("fail_reason") or "",
        "quality_gate_pass": meta.get("quality_gate_pass"),
        "delivery_label": (
            "成片"
            if level == "l1"
            else ("分镜草稿" if level == "l0" else "未渲染")
        ),
    }


EXTRACT_TOPIC_PROMPT = """你是短视频策划。根据用户与助手的对话，判断是否已有可拍的口播主题，并尽量抽出传播要素。
只输出 JSON，不要 markdown：
{{
  "ready": true,
  "topic": "一句话主题（可作视频标题种子）",
  "brief": "卖点/钩子摘要，2-4句",
  "audience": "目标受众（若对话未提则空字符串）",
  "scene_setting": "具体使用场景/痛点场景（若未提则空）",
  "platform": "平台如抖音/视频号/小红书（未提则空）",
  "cta": "希望观众做什么（未提则空）",
  "reason": "ready=false 时说明缺什么"
}}
规则：
- 用户已明确说出想做什么短视频/口播，并给出主题、卖点或内容方向 → ready 必须为 true，并填写 topic。
- 仅当完全是闲聊、问候、或用户自己说还没想好主题时，ready 才为 false。
- 不要因为还可以再优化文案就把 ready 设为 false。
对话记录：
{transcript}
"""


def _heuristic_topic_from_transcript(transcript: str) -> dict[str, Any]:
    user_lines: list[str] = []
    for line in transcript.splitlines():
        line = line.strip()
        m = re.match(r"^(用户|user):\s*(.+)$", line, flags=re.I)
        if m:
            user_lines.append(m.group(2).strip())
    if not user_lines:
        return {
            "ready": False,
            "topic": "",
            "brief": "",
            "audience": "",
            "scene_setting": "",
            "platform": "",
            "cta": "",
            "reason": "对话太短，还没有可拍的主题",
        }
    last = user_lines[-1]
    # Prefer a line that looks like a video brief
    pick = last
    for u in reversed(user_lines):
        if any(k in u for k in ("短视频", "口播", "视频", "主题", "卖点")):
            pick = u
            break
    if len(pick) < 4:
        return {
            "ready": False,
            "topic": "",
            "brief": "",
            "audience": "",
            "scene_setting": "",
            "platform": "",
            "cta": "",
            "reason": "无法从对话提炼主题",
        }
    return {
        "ready": True,
        "topic": pick[:80],
        "brief": pick[:200],
        "audience": "",
        "scene_setting": "",
        "platform": "",
        "cta": "",
        "reason": "heuristic_user_message",
    }


async def extract_topic_from_transcript(
    llm: Any,
    *,
    transcript: str,
    model: str = "",
) -> dict[str, Any]:
    """LLM extract topic/brief from a chat transcript."""
    text = (transcript or "").strip()
    if len(text) < 8:
        return {
            "ready": False,
            "topic": "",
            "brief": "",
            "audience": "",
            "scene_setting": "",
            "platform": "",
            "cta": "",
            "reason": "对话太短，还没有可拍的主题",
        }
    prompt = EXTRACT_TOPIC_PROMPT.format(transcript=text[:6000])
    raw = await llm.chat_completion(
        [{"role": "user", "content": prompt}],
        model=model,
        temperature=0.2,
        max_tokens=700,
    )
    content = ((raw.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    try:
        data = _extract_json(content)
    except Exception:
        return _heuristic_topic_from_transcript(text)

    ready = bool(data.get("ready"))
    topic = (data.get("topic") or "").strip()
    brief = (data.get("brief") or "").strip()
    reason = (data.get("reason") or "").strip()
    extras = {
        "audience": (data.get("audience") or "").strip()[:80],
        "scene_setting": (data.get("scene_setting") or "").strip()[:120],
        "platform": (data.get("platform") or "").strip()[:40],
        "cta": (data.get("cta") or "").strip()[:80],
    }

    # Small local models often set ready=false even with a clear topic — salvage.
    if topic and not ready:
        ready = True
        reason = reason or "salvaged_topic_despite_ready_false"
    if not topic:
        heur = _heuristic_topic_from_transcript(text)
        if heur.get("ready"):
            return heur
        return {
            "ready": False,
            "topic": "",
            "brief": brief,
            **extras,
            "reason": reason or heur.get("reason") or "无法从对话提炼主题",
        }
    return {
        "ready": ready,
        "topic": topic[:80],
        "brief": brief[:500],
        **extras,
        "reason": reason,
    }


async def _run(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _out, err = await proc.communicate()
    if proc.returncode != 0:
        exe = Path(cmd[0]).name if cmd else "cmd"
        detail = _stderr_gist(err.decode(errors="replace"))
        raise RuntimeError(f"{exe} exit {proc.returncode}: {detail}")


# ffmpeg/ffprobe print a long version+configuration banner before the real
# error, so a head-truncated stderr shows nothing useful.
_NOISE_PREFIXES = (
    "ffmpeg version",
    "ffprobe version",
    "built with",
    "configuration:",
    "lib",
    "Input #",
    "Output #",
    "Stream #",
    "Metadata:",
    "Duration:",
    "  ",
)


def _stderr_gist(raw: str, limit: int = 400) -> str:
    lines = [ln.rstrip() for ln in (raw or "").splitlines() if ln.strip()]
    signal = [ln for ln in lines if not ln.startswith(_NOISE_PREFIXES)]
    keep = signal or lines
    if not keep:
        return "no stderr"
    # Real cause is at the tail (e.g. "No such filter: 'drawtext'").
    gist = " | ".join(keep[-3:])
    return gist[:limit]


def _tts_networkish(msg: str) -> bool:
    return any(
        x in msg
        for x in (
            "nodename nor servname",
            "Cannot connect",
            "ClientConnector",
            "gaierror",
            "Name or service not known",
            "Temporary failure",
            "timed out",
            "Timeout",
            "NoAudioReceived",
            "websocket",
            "WSServerHandshake",
            "503",
            "429",
        )
    )


def _unlink_quiet(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _audio_duration(path: Path) -> float:
    # Prefer ffprobe
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(r.stdout.strip())
    except Exception:
        if path.suffix.lower() == ".wav":
            with wave.open(str(path), "rb") as w:
                return w.getnframes() / float(w.getframerate())
        return 3.0


async def synthesize_tts(
    text: str, out_mp3: Path, *, voice: str = "zh-CN-XiaoxiaoNeural"
) -> float:
    speak = speakable_narration(text)
    if not speak:
        raise RuntimeError("旁白为空，无法配音")
    out_mp3.parent.mkdir(parents=True, exist_ok=True)

    # Prefer in-process API (same interpreter as the server). Shelling out to a
    # Homebrew edge-tts on another Python often fails intermittently and the
    # long --text argv also hides stderr in truncated error messages.
    use_api = False
    try:
        import edge_tts  # noqa: F401

        use_api = True
    except ImportError:
        edge_tts = None  # type: ignore[assignment]
    edge_cli = shutil.which("edge-tts")

    last_err: BaseException | None = None
    for attempt in range(3):
        _unlink_quiet(out_mp3)
        try:
            if use_api:
                communicate = edge_tts.Communicate(speak, voice)
                await communicate.save(str(out_mp3))
            elif edge_cli:
                await _run(
                    [
                        edge_cli,
                        "--voice",
                        voice,
                        "--text",
                        speak,
                        "--write-media",
                        str(out_mp3),
                    ]
                )
            else:
                raise RuntimeError("未安装 edge-tts（pip install edge-tts）")
            if out_mp3.is_file() and out_mp3.stat().st_size > 0:
                return _audio_duration(out_mp3)
            raise RuntimeError("edge-tts 未写出音频文件")
        except BaseException as exc:  # noqa: BLE001
            last_err = exc
            _unlink_quiet(out_mp3)
            # If in-process API keeps failing, try CLI once as last resort.
            if use_api and edge_cli and attempt == 1:
                use_api = False
            if attempt < 2:
                await asyncio.sleep(0.8 * (attempt + 1))
                continue
            break
    msg = str(last_err or "")
    if _tts_networkish(msg):
        raise RuntimeError(
            "语音合成失败：连不上 Microsoft TTS（speech.platform.bing.com）。"
            "请检查网络后重试草稿。"
        ) from last_err
    # Keep the real exception detail; never dump the spoken text / long argv.
    detail = (msg or "unknown").replace(speak, "…")[:220]
    raise RuntimeError(f"语音合成失败：{detail}") from last_err


_DENSIFY_FILLER_RE = re.compile(
    r"(这里补一句可执行细节[^。！？]*[。！？]?|"
    r"把这一步写进你的笔记[^。！？]*[。！？]?|"
    r"别只记名词[^。！？]*[。！？]?)",
)


def speakable_narration(text: str) -> str:
    """Strip densify meta filler and normalize for edge-tts."""
    raw = (text or "").strip()
    if not raw:
        return ""
    cleaned = _DENSIFY_FILLER_RE.sub("", raw)
    cleaned = re.sub(r"[「」『』]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Prefer original if strip wiped everything
    speak = cleaned or re.sub(r"[「」『』]", "", raw)
    # edge-tts is happier with shorter utterances; hard cap ~280 chars
    if len(speak) > 280:
        cut = speak[:280]
        # break at last sentence end if possible
        m = re.search(r"^(.*[。！？])", cut)
        speak = (m.group(1) if m else cut).strip()
    return speak


def _spoken_pad_clause(topic: str, role: str) -> str:
    """Natural spoken padding (never meta instructions)."""
    short = (topic or "这一步")[:24]
    by_role = {
        "hook": f"先记住：别被名词吓住，今天只把「{short}」跑通最小一步。",
        "pain": f"卡点通常不是工具本身，而是没有验证「{short}」能不能落地。",
        "steps": f"操作时盯住输出结果，确认「{short}」这一步真的成功了再往下。",
        "value": f"你可以现在就试：对着「{short}」做完这一步，马上看结果对不对。",
        "proof": f"用一次可复现的结果说话，比收藏十篇关于「{short}」的文章更管用。",
        "compare": f"选型时只问一句：这个选择能不能更快帮你验证「{short}」。",
        "pitfall": f"最常见坑是一次上全功能；先最小闭环，再扩展「{short}」。",
        "cta": f"有用就收藏，下次直接复用「{short}」这条路径。",
    }
    return by_role.get((role or "").lower()) or (
        f"先把「{short}」拆成最小一步，当场验证能跑通，再记进笔记。"
    )


def _font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_faux_terminal(
    draw: ImageDraw.ImageDraw,
    *,
    box: tuple[int, int, int, int],
    accent: tuple[int, int, int],
    seed: int,
    caption: str,
    reveal: float = 1.0,
    blink: bool = True,
) -> None:
    """High-contrast terminal plate; `reveal` 0..1 types lines in for local animation."""
    x0, y0, x1, y1 = box
    draw.rounded_rectangle([x0, y0, x1, y1], radius=18, fill=(8, 10, 14), outline=accent, width=3)
    draw.rectangle([x0, y0, x1, y0 + 44], fill=(28, 32, 40))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = x0 + 22 + i * 28
        draw.ellipse([cx, y0 + 14, cx + 16, y0 + 30], fill=c)
    mono = _font(28)
    green = (72, 220, 140)
    dim = (48, 110, 78)
    lines = [
        "$ agent run --scene",
        "[boot] loading context… OK",
        "████  LIVE  ████",
        ">>> narrator attached",
        caption[:22] or "ready.",
        "latency 12ms | sync ok",
        "ctrl+c to yield control",
    ]
    reveal = max(0.05, min(1.0, float(reveal)))
    visible = max(1, int(round(len(lines) * reveal)))
    y = y0 + 64
    for i, line in enumerate(lines[:visible]):
        shade = green if i % 2 == 0 else dim
        ox = 18 + ((i * 17 + seed * 9) % 40)
        # Partial last line = typing effect
        if i == visible - 1 and reveal < 0.99:
            frac = (reveal * len(lines)) - (visible - 1)
            cut = max(1, int(len(line) * max(0.15, min(1.0, frac))))
            line = line[:cut]
        draw.text((x0 + ox, y), line, font=mono, fill=shade)
        y += 46
        if y > y1 - 36:
            break
    cursor_y = y0 + 64 + max(0, visible - 1) * 46
    if blink:
        draw.rectangle([x0 + 40, cursor_y, x0 + 58, cursor_y + 30], fill=accent)


def _split_visual_board_shot(visual: str) -> tuple[str, str]:
    """visual may be `板式｜镜头` — return (board, shot)."""
    text = (visual or "").strip()
    if "｜" in text:
        a, b = text.split("｜", 1)
        return a.strip(), b.strip()
    if "|" in text and re.search(r"[\u4e00-\u9fff]", text):
        a, b = text.split("|", 1)
        return a.strip(), b.strip()
    return text, ""


def _content_bits(narration: str, visual: str, *, limit: int = 4) -> list[str]:
    """Prefer concrete clauses from narration / visual board over filler padding."""
    board, _shot = _split_visual_board_shot(visual)
    bits: list[str] = []
    for chunk in re.split(r"[。！？；;\n]", narration or ""):
        c = chunk.strip()
        # Skip densify filler blobs (legacy + spoken pads are kept)
        if not c or "这里补一句可执行细节" in c:
            continue
        if c.startswith("把这一步写进你的笔记"):
            continue
        bits.append(c[:28])
        if len(bits) >= limit:
            return bits
    for chunk in re.split(r"[+／/、,，]", board or ""):
        c = chunk.strip()
        if c and c not in bits:
            bits.append(c[:22])
        if len(bits) >= limit:
            break
    return bits


def _draw_visual_footnote(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    visual: str,
    muted: tuple[int, int, int],
    font: Any,
) -> None:
    board, _shot = _split_visual_board_shot(visual)
    if not board:
        return
    x0, _y0, x1, y1 = box
    draw.multiline_text(
        (x0 + 36, y1 - 72),
        _wrap(board[:42], 18),
        font=font,
        fill=muted,
        spacing=4,
    )


def _draw_role_plate(
    draw: ImageDraw.ImageDraw,
    *,
    role: str,
    box: tuple[int, int, int, int],
    accent: tuple[int, int, int],
    ink: tuple[int, int, int],
    muted: tuple[int, int, int],
    on_screen: str,
    narration: str,
    visual: str,
    seed: int,
    reveal: float,
    blink: bool,
) -> None:
    """Role-specific center plate — hero text from on_screen, footnote from visual board."""
    x0, y0, x1, y1 = box
    panel = (12, 12, 16) if ink[0] > 128 else (255, 252, 246)
    hero = _font(64)
    body = _font(40)
    small = _font(30)
    big = _font(120)
    board, _shot = _split_visual_board_shot(visual)
    text = (on_screen or board or narration or "")[:40]
    bits = _content_bits(narration, visual, limit=4)

    if role == "hook":
        draw.rounded_rectangle([x0, y0, x1, y1], radius=28, fill=panel, outline=accent, width=4)
        num = str((seed * 37) % 90 + 10)
        draw.text((x0 + 48, y0 + 80), num, font=big, fill=accent)
        draw.text((x0 + 48 + 200, y0 + 140), "秒说清", font=hero, fill=ink)
        draw.multiline_text((x0 + 48, y0 + 320), _wrap(text, 10), font=hero, fill=ink, spacing=12)
        _draw_visual_footnote(draw, box, visual, muted, small)
        return

    if role == "pain":
        draw.rounded_rectangle([x0, y0, x1, y1], radius=28, fill=(20, 14, 10), outline=accent, width=4)
        draw.text((x0 + 40, y0 + 60), "「", font=big, fill=accent)
        draw.multiline_text(
            (x0 + 80, y0 + 200),
            _wrap(text or "信息很多，落地很少", 9),
            font=hero,
            fill=ink,
            spacing=14,
        )
        draw.text((x1 - 120, y1 - 140), "」", font=big, fill=accent)
        _draw_visual_footnote(draw, box, visual, muted, small)
        return

    if role in ("steps", "value"):
        draw.rounded_rectangle([x0, y0, x1, y1], radius=24, fill=panel, outline=accent, width=3)
        draw.text((x0 + 40, y0 + 36), text[:16] or "可执行要点", font=hero, fill=ink)
        lines = bits[:3] or [narration[:24] or "要点一", "要点二", "要点三"]
        for i, line in enumerate(lines[:3]):
            yy = y0 + 160 + i * 120
            draw.ellipse([x0 + 40, yy, x0 + 100, yy + 60], fill=accent)
            draw.text((x0 + 58, yy + 8), str(i + 1), font=hero, fill=(10, 10, 12))
            draw.text((x0 + 130, yy + 12), (line.strip()[:18]), font=body, fill=ink)
        _draw_visual_footnote(draw, box, visual, muted, small)
        return

    if role in ("compare", "proof"):
        mid = (x0 + x1) // 2
        draw.rounded_rectangle([x0, y0, mid - 12, y1], radius=20, fill=(18, 18, 24), outline=accent, width=3)
        draw.rounded_rectangle([mid + 12, y0, x1, y1], radius=20, fill=(24, 18, 18), outline=(255, 140, 100), width=3)
        left = (bits[0] if bits else "之前/方案A")[:14]
        right = (bits[1] if len(bits) > 1 else "之后/方案B")[:14]
        draw.text((x0 + 36, y0 + 40), "A", font=hero, fill=accent)
        draw.text((mid + 48, y0 + 40), "B", font=hero, fill=(255, 140, 100))
        draw.multiline_text((x0 + 36, y0 + 160), _wrap(left, 7), font=body, fill=ink, spacing=8)
        draw.multiline_text((mid + 48, y0 + 160), _wrap(right, 7), font=body, fill=ink, spacing=8)
        draw.text((x0 + 36, y1 - 80), text[:16], font=small, fill=muted)
        return

    if role == "pitfall":
        draw.rounded_rectangle([x0, y0, x1, y1], radius=24, fill=(36, 12, 16), outline=accent, width=5)
        draw.rectangle([x0, y0, x1, y0 + 90], fill=accent)
        draw.text((x0 + 40, y0 + 22), "避坑", font=hero, fill=(10, 10, 12))
        draw.multiline_text((x0 + 40, y0 + 140), _wrap(text or "别一上来全功能", 10), font=hero, fill=ink, spacing=12)
        tip = (bits[0] if bits else narration[:30])[:40]
        draw.multiline_text((x0 + 40, y0 + 360), _wrap(tip, 14), font=body, fill=muted, spacing=8)
        _draw_visual_footnote(draw, box, visual, muted, small)
        return

    if role == "cta":
        draw.rounded_rectangle([x0, y0, x1, y1], radius=28, fill=panel, outline=accent, width=4)
        draw.rounded_rectangle([x0 + 80, y0 + 220, x1 - 80, y0 + 420], radius=40, fill=accent)
        draw.multiline_text(
            (x0 + 120, y0 + 270),
            _wrap(text or "收藏 + 评论", 8),
            font=hero,
            fill=(10, 10, 12),
            spacing=10,
        )
        draw.text((x0 + 80, y1 - 160), "下一步就做这一件", font=body, fill=ink)
        _draw_visual_footnote(draw, box, visual, muted, small)
        return

    if role == "context":
        draw.rounded_rectangle([x0, y0, x1, y1], radius=24, fill=panel, outline=accent, width=3)
        draw.text((x0 + 40, y0 + 40), "定义", font=small, fill=accent)
        draw.multiline_text((x0 + 40, y0 + 100), _wrap(text, 10), font=hero, fill=ink, spacing=12)
        if board:
            draw.multiline_text((x0 + 40, y0 + 420), _wrap(board, 16), font=small, fill=muted, spacing=6)
        return

    if role == "thesis":
        draw.rounded_rectangle([x0, y0, x1, y1], radius=24, fill=(22, 20, 12), outline=accent, width=4)
        draw.rectangle([x0, y0, x0 + 18, y1], fill=accent)
        draw.text((x0 + 48, y0 + 40), "THESIS · 论点", font=small, fill=accent)
        draw.multiline_text(
            (x0 + 48, y0 + 120),
            _wrap(text or "盯关键变量，不盯热闹", 9),
            font=hero,
            fill=ink,
            spacing=14,
        )
        tip = (bits[0] if bits else narration[:36])[:48]
        draw.multiline_text((x0 + 48, y0 + 420), _wrap(tip, 16), font=body, fill=muted, spacing=8)
        return

    if role == "evidence":
        draw.rounded_rectangle([x0, y0, x1, y1], radius=24, fill=panel, outline=accent, width=3)
        draw.text((x0 + 40, y0 + 36), "EVIDENCE", font=small, fill=accent)
        draw.multiline_text((x0 + 40, y0 + 90), _wrap(text[:20] or "硬指标", 10), font=hero, fill=ink, spacing=10)
        # faux sparkline / bars — caption from content, not only seed
        base_y = y1 - 140
        heights = [40 + ((seed * 17 + i * 31) % 160) for i in range(8)]
        gap = (x1 - x0 - 80) // 8
        for i, ht in enumerate(heights):
            bx = x0 + 40 + i * gap
            color = accent if i == len(heights) - 1 else (60, 90, 110)
            draw.rectangle([bx, base_y - ht, bx + gap - 12, base_y], fill=color)
        fact = (bits[0] if bits else board or "可核对的事实")[:28]
        draw.text((x0 + 40, y1 - 100), fact, font=small, fill=muted)
        return

    if role == "pattern":
        draw.rounded_rectangle([x0, y0, x1, y1], radius=24, fill=(18, 14, 12), outline=accent, width=4)
        draw.text((x0 + 40, y0 + 36), "PATTERN · 规律", font=small, fill=accent)
        draw.multiline_text(
            (x0 + 40, y0 + 100),
            _wrap(text or "热闹先行，兑现滞后", 9),
            font=hero,
            fill=ink,
            spacing=12,
        )
        pts = []
        for i in range(7):
            px = x0 + 60 + i * ((x1 - x0 - 120) // 6)
            py = y0 + 420 + (30 if i % 2 == 0 else -40) + (i * 8)
            pts.append((px, py))
        draw.line(pts, fill=accent, width=5)
        for px, py in pts:
            draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill=accent)
        _draw_visual_footnote(draw, box, visual, muted, small)
        return

    if role == "verdict":
        draw.rounded_rectangle([x0, y0, x1, y1], radius=28, fill=(12, 28, 20), outline=accent, width=5)
        draw.rectangle([x0, y0, x1, y0 + 100], fill=accent)
        draw.text((x0 + 40, y0 + 28), "VERDICT · 结论已清晰", font=hero, fill=(10, 10, 12))
        draw.multiline_text(
            (x0 + 40, y0 + 160),
            _wrap(text or "先验证，再加码", 9),
            font=hero,
            fill=ink,
            spacing=12,
        )
        action_bit = (bits[0] if bits else "写下行动点")[:40]
        draw.rounded_rectangle([x0 + 40, y1 - 200, x1 - 40, y1 - 80], radius=20, fill=accent)
        draw.multiline_text(
            (x0 + 70, y1 - 170),
            _wrap(action_bit, 14),
            font=body,
            fill=(10, 10, 12),
            spacing=6,
        )
        return

    # Fallback: terminal with content-aligned caption (prefer on_screen)
    _draw_faux_terminal(
        draw,
        box=box,
        accent=accent,
        seed=seed,
        caption=(on_screen or board or narration or "")[:48],
        reveal=reveal,
        blink=blink,
    )
    _draw_visual_footnote(draw, box, visual, muted, small)


def render_scene_image(
    out_png: Path,
    *,
    title: str,
    cover_hook: str = "",
    visual: str = "",
    narration: str = "",
    on_screen: str = "",
    role: str = "value",
    mood: str = "",
    scene_num: int,
    total: int,
    hashtags: Optional[list[str]] = None,
    cta: str = "",
    bg_theme: str = "night",
    reveal: float = 1.0,
    anim_shift: int = 0,
) -> None:
    """Vertical 1080x1920 card — role-specific plates so scenes look different."""
    w, h = 1080, 1920
    role_key = (role or "value").lower()
    if role_key not in ROLE_COLORS:
        role_key = "value"
    accent, _role_base = ROLE_COLORS[role_key]
    theme_id = bg_theme if bg_theme in BG_THEMES else "night"
    # Keep one brand look per project — do not hop themes every 3rd scene.
    theme = BG_THEMES.get(theme_id) or BG_THEMES["night"]
    base = tuple(theme["base"])
    ink = tuple(theme.get("ink") or (250, 250, 252))
    muted = (160, 165, 175) if ink[0] > 128 else (90, 85, 80)
    pattern = theme.get("pattern") or "wash"

    img = Image.new("RGB", (w, h), base)
    draw = ImageDraw.Draw(img)

    for y in range(h):
        t = y / h
        color = (
            int(base[0] + (accent[0] - base[0]) * 0.28 * (1 - t)),
            int(base[1] + (accent[1] - base[1]) * 0.22 * (1 - t)),
            int(base[2] + (accent[2] - base[2]) * 0.30 * (1 - t)),
        )
        draw.line([(0, y), (w, y)], fill=color)

    for i in range(-2, 6):
        x = -200 + i * 220 + scene_num * 47
        draw.polygon(
            [(x, 0), (x + 90, 0), (x + 520, h), (x + 430, h)],
            fill=(
                min(255, base[0] + 18 + i * 2),
                min(255, base[1] + 14 + i * 2),
                min(255, base[2] + 22 + i * 2),
            ),
        )

    if pattern == "stars":
        for i in range(70):
            x = (i * 97 + scene_num * 13) % w
            y = (i * 53 + scene_num * 29) % h
            r = 1 + (i % 3)
            draw.ellipse([x, y, x + r, y + r], fill=(220, 230, 255))
    elif pattern == "grid":
        for x in range(0, w, 48):
            draw.line([(x, 0), (x, h)], fill=(48, 48, 58))
        for y in range(0, h, 48):
            draw.line([(0, y), (w, y)], fill=(48, 48, 58))
    elif pattern == "neon":
        draw.rectangle([36, 90, w - 36, 460], outline=accent, width=5)
    elif pattern == "paper":
        for i in range(0, h, 8):
            shade = 232 + (i // 8) % 3
            draw.line([(0, i), (w, i)], fill=(shade, shade - 4, shade - 10))
    elif pattern == "leaves":
        for i in range(24):
            x = (i * 71 + 20) % w
            y = (i * 101 + 40) % h
            draw.ellipse([x, y, x + 34, y + 16], outline=(40, 110, 70), width=2)
    elif pattern == "candles":
        # finance-desk vibe: soft candle bars in the background
        for i in range(18):
            bx = 40 + i * 58
            ht = 80 + ((scene_num * 19 + i * 41) % 220)
            top = 520 + ((i * 13) % 80)
            up = i % 3 != 0
            col = (40, 140, 100) if up else (160, 60, 70)
            draw.rectangle([bx, top, bx + 28, top + ht], fill=col)
            draw.line([(bx + 14, top - 24), (bx + 14, top + ht + 24)], fill=col, width=2)
    elif pattern == "wash":
        draw.ellipse([-220, -120, 560, 640], outline=accent, width=3)

    draw.rectangle([0, 0, 14, h], fill=accent)
    draw.rectangle([0, 0, w, 22], fill=accent)

    title_font = _font(52)
    hero_font = _font(72)
    small = _font(30)
    badge = _font(34)

    label = ROLE_LABELS.get(role_key, "干货")
    pill = f" {label} · {scene_num}/{total} "
    draw.rounded_rectangle([52, 70, 52 + 20 * len(pill), 132], radius=24, fill=accent)
    draw.text((68, 80), pill, font=badge, fill=(10, 10, 12))

    hero = (on_screen or cover_hook or title or "短视频")[:18]
    hero_y = 150 + int((1.0 - max(0.35, min(1.0, reveal))) * 36)
    draw.multiline_text((76, hero_y + 4), _wrap(hero, 9), font=hero_font, fill=(0, 0, 0), spacing=10)
    draw.multiline_text((72, hero_y), _wrap(hero, 9), font=hero_font, fill=ink, spacing=10)

    if mood:
        draw.text((72, 400), f"情绪 · {mood}", font=small, fill=accent)

    _draw_role_plate(
        draw,
        role=role_key,
        box=(48, 460, w - 48, 1180),
        accent=accent,
        ink=ink,
        muted=muted,
        on_screen=on_screen,
        narration=narration,
        visual=visual,
        seed=scene_num + anim_shift,
        reveal=reveal,
        blink=(anim_shift % 2 == 0),
    )

    panel_fill = (12, 12, 16) if ink[0] > 128 else (255, 252, 246)
    draw.rounded_rectangle([48, 1220, w - 48, 1580], radius=20, fill=panel_fill, outline=accent, width=2)
    body = (narration or "")[:140]
    draw.multiline_text(
        (72, 1260),
        _wrap(body, 14),
        font=_font(38),
        fill=ink if ink[0] > 128 else (30, 28, 24),
        spacing=10,
    )

    for i in range(min(total, 16)):
        cx = 80 + (i % 8) * 36
        cy = 1620 + (i // 8) * 28
        r = 7
        fill = accent if i + 1 == scene_num else muted
        draw.ellipse([cx, cy, cx + r * 2, cy + r * 2], fill=fill)

    footer = title[:22]
    if role_key == "cta" and cta:
        footer = cta[:24]
    draw.text((72, 1700), footer, font=title_font, fill=ink)
    tags = "  ".join(f"#{t}" for t in (hashtags or [])[:3])
    if tags:
        draw.text((72, 1780), tags[:42], font=small, fill=muted)

    draw.rectangle([0, h - 16, w, h], fill=(30, 30, 36))
    draw.rectangle([0, h - 16, int(w * scene_num / max(total, 1)), h], fill=accent)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)



def _wrap(text: str, width: int) -> str:
    lines = []
    buf = ""
    for ch in text:
        buf += ch
        if len(buf) >= width:
            lines.append(buf)
            buf = ""
    if buf:
        lines.append(buf)
    return "\n".join(lines[:8])


def _accent_hex(role: str = "value") -> str:
    rgb, _ = ROLE_COLORS.get((role or "value").lower(), ROLE_COLORS["value"])
    return f"0x{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def _zoompan_xy(pan: str, n: int) -> tuple[str, str]:
    """Progress on/{n} goes ~0→1 across the clip."""
    p = f"on/{n}"
    if pan == "up":
        return ("(iw-iw/zoom)/2", f"(ih-ih/zoom)*(1-0.08-0.84*{p})")
    if pan == "down":
        return ("(iw-iw/zoom)/2", f"(ih-ih/zoom)*(0.08+0.84*{p})")
    if pan == "left":
        return (f"(iw-iw/zoom)*(1-0.08-0.84*{p})", "(ih-ih/zoom)/2")
    if pan == "right":
        return (f"(iw-iw/zoom)*(0.08+0.84*{p})", "(ih-ih/zoom)/2")
    if pan == "diag":
        return (
            f"(iw-iw/zoom)*(0.1+0.8*{p})",
            f"(ih-ih/zoom)*(0.1+0.8*{p})",
        )
    return (
        f"(iw-iw/zoom)*(0.42+0.16*{p})",
        f"(ih-ih/zoom)*(0.38+0.20*{p})",
    )


def _build_motion_vf(
    *,
    motion: str,
    frames: int,
    dur: float,
    fade_in: float,
    fade_out: float,
    fade_out_start: float,
    accent_hex: str,
) -> str:
    motion_key = motion if motion in MOTIONS else "kenburns"
    spec = MOTIONS[motion_key]
    z0 = float(spec["zoom_start"])
    z1 = float(spec["zoom_end"])
    pan = str(spec.get("pan") or "center")
    n = max(frames - 1, 1)

    if abs(z1 - z0) < 0.001 and motion_key == "static":
        base = "scale=1080:1920,format=yuv420p"
    else:
        x_expr, y_expr = _zoompan_xy(pan, n)
        z_expr = f"'{z0}+({z1}-{z0})*on/{n}'"
        # With -loop 1 -framerate fps, each input frame must map to 1 output frame (d=1).
        # Using d=N here resets the zoom every input frame and looks almost static.
        base = (
            f"scale=2160:3840,"
            f"zoompan=z={z_expr}:x='{x_expr}':y='{y_expr}'"
            f":d=1:s=1080x1920:fps=30"
        )

    # Commas inside filter expressions must be \, for ffmpeg filtergraph parsing.
    c = r"\,"
    overlays = (
        f"drawbox=x=0:y=0:w=iw:h=10:color={accent_hex}@0.95:t=fill,"
        f"drawbox=x='mod(t*280{c}w+160)-160':y=48:w=160:h=6:color={accent_hex}@0.75:t=fill,"
        f"drawbox=x=0:y=ih-14:w='max(12{c}iw*t/{dur:.3f})':h=14:color={accent_hex}@0.92:t=fill"
    )
    fades = (
        f"fade=t=in:st=0:d={fade_in:.3f},"
        f"fade=t=out:st={fade_out_start:.3f}:d={fade_out:.3f}"
    )
    return f"{base},{overlays},{fades}"


def write_scene_keyframes(
    key_dir: Path,
    *,
    n_keys: int,
    **card_kwargs: Any,
) -> list[Path]:
    """Write progressive reveal plates for typing + camera animation."""
    key_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    n_keys = max(4, min(12, int(n_keys)))
    for i in range(n_keys):
        # Ease-in reveal so early frames change fast (reads as typing)
        t = (i + 1) / n_keys
        reveal = 0.12 + 0.88 * (t ** 0.75)
        path = key_dir / f"k_{i:02d}.png"
        render_scene_image(
            path,
            reveal=reveal,
            anim_shift=i,
            **card_kwargs,
        )
        paths.append(path)
    return paths


async def render_scene_clip(
    image: Path,
    audio: Path,
    out_mp4: Path,
    duration: float,
    *,
    motion: str = "kenburns",
    role: str = "value",
    keyframes: Optional[list[Path]] = None,
) -> None:
    """Keyframe plates (or still) + audio → vertical clip with zoom/pan + HUD."""
    dur = max(duration, 0.8)
    fps = 30
    frames = max(1, int(round(dur * fps)))
    fade_in = min(0.22, dur / 5)
    fade_out = min(0.32, dur / 4)
    fade_out_start = max(0.0, dur - fade_out)
    accent = _accent_hex(role)
    vf = _build_motion_vf(
        motion=motion,
        frames=frames,
        dur=dur,
        fade_in=fade_in,
        fade_out=fade_out,
        fade_out_start=fade_out_start,
        accent_hex=accent,
    )

    keys = list(keyframes or [])
    if len(keys) >= 2:
        # Low-fps plate stream → fps=30 duplicates → zoompan advances each output frame
        plate_fps = max(len(keys) / dur, 0.5)
        # Prepend fps=30 before zoompan chain (vf already starts with scale/zoompan)
        vf = f"fps={fps}," + vf
        cmd = [
            "ffmpeg",
            "-y",
            "-framerate",
            f"{plate_fps:.4f}",
            "-i",
            str(keys[0].parent / "k_%02d.png"),
            "-i",
            str(audio),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-t",
            f"{dur:.3f}",
            "-r",
            str(fps),
            "-vf",
            vf,
            str(out_mp4),
        ]
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(fps),
            "-i",
            str(image),
            "-i",
            str(audio),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-t",
            f"{dur:.3f}",
            "-r",
            str(fps),
            "-vf",
            vf,
            str(out_mp4),
        ]
    await _run(cmd)


async def concat_clips(clips: list[Path], out_mp4: Path) -> None:
    """Re-encode concat so zoompan clips share one timebase."""
    lst = out_mp4.parent / "concat.txt"
    lines = [f"file '{c.resolve()}'" for c in clips]
    lst.write_text("\n".join(lines), encoding="utf-8")
    await _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lst),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(out_mp4),
        ]
    )


def _cjk_fontfile() -> str:
    for path in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ):
        if Path(path).is_file():
            return path
    return ""


def _ffmpeg_drawtext_escape(text: str) -> str:
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "%%")
    )


@lru_cache(maxsize=8)
def ffmpeg_has_filter(name: str) -> bool:
    """Homebrew ffmpeg 8.x ships without libfreetype, so drawtext may be absent."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    pattern = re.compile(rf"^\s*\S+\s+{re.escape(name)}\s", re.M)
    return bool(pattern.search(r.stdout or ""))


def write_caption_overlay(out_png: Path, text: str, *, width: int, height: int) -> Path:
    """Transparent caption plate used when ffmpeg has no drawtext filter."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _font(54)
    caption = (text or "").strip()
    box = draw.textbbox((0, 0), caption, font=font)
    x = max(0, (width - (box[2] - box[0])) // 2 - box[0])
    y = int(height * 0.10)
    draw.text(
        (x, y),
        caption,
        font=font,
        fill=(255, 255, 255, 255),
        stroke_width=4,
        stroke_fill=(0, 0, 0, 217),
    )
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    return out_png


async def mux_video_audio(
    video: Path,
    audio: Path,
    out_mp4: Path,
    duration: float,
    *,
    overlay_text: str = "",
) -> None:
    """Loop/crop Agnes video to match TTS; burn in on_screen caption when possible."""
    dur = max(duration, 0.8)
    base_vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    caption = (overlay_text or "").strip()[:22]
    font = _cjk_fontfile()

    plate: Path | None = None
    vf = base_vf
    if caption and font and ffmpeg_has_filter("drawtext"):
        esc = _ffmpeg_drawtext_escape(caption)
        vf += (
            f",drawtext=fontfile={font}:text='{esc}':fontsize=54:fontcolor=white"
            ":borderw=4:bordercolor=black@0.85:x=(w-text_w)/2:y=h*0.10"
        )
    elif caption:
        plate = write_caption_overlay(
            out_mp4.with_name(f"{out_mp4.stem}_caption.png"),
            caption,
            width=1080,
            height=1920,
        )

    cmd = ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(video), "-i", str(audio)]
    if plate is not None:
        cmd += ["-i", str(plate)]
        cmd += [
            "-filter_complex",
            f"[0:v]{base_vf}[bg];[bg][2:v]overlay=0:0:format=auto[v]",
            "-map",
            "[v]",
        ]
    else:
        cmd += ["-vf", vf, "-map", "0:v:0"]
    cmd += [
        "-t",
        f"{dur:.3f}",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(out_mp4),
    ]
    await _run(cmd)


_ROLE_SHOT_HINTS: dict[str, str] = {
    "hook": "urgent vertical open, bold subject in frame, slow push-in",
    "pain": "frustrated creator at desk, dim light, shallow depth of field",
    "context": "clean explainer desk shot, product or UI on monitor",
    "thesis": "analysis desk with notes and one key chart in focus",
    "evidence": "close-up of charts and numbers on a laptop screen",
    "pattern": "time-lapse of trend line growing on a dark monitor",
    "verdict": "decisive desk shot, checklist or green confirm moment",
    "steps": "hands-on tutorial angle, keyboard and terminal readable",
    "value": "practical tip card vibe with concrete props on desk",
    "compare": "split composition feel, two options side by side on desk",
    "proof": "before/after workspace contrast, documentary style",
    "pitfall": "warning atmosphere, red accent light, mistake on screen",
    "cta": "friendly creator facing camera zone, invite action",
}


def _board_to_cinematic_shot(
    *,
    visual: str,
    role: str,
    on_screen: str,
    title: str,
    narration: str,
) -> str:
    board, shot = _split_visual_board_shot(visual)
    if shot and len(shot) >= 8:
        return shot
    # Translate common board jargon into a concrete camera description
    src = board or on_screen or title
    translations = (
        ("数据条", "bar charts and KPI numbers on a dark analytics dashboard"),
        ("趋势", "rising line chart on a monitor, subtle camera push"),
        ("折线", "line chart trending across a widescreen display"),
        ("清单", "checklist on a notepad next to a laptop"),
        ("对比", "two options laid out on a desk, split framing"),
        ("大数字", "oversized key number graphic in a cinematic desk scene"),
        ("时间轴", "timeline graphic on a screen with soft desk lighting"),
        ("结论", "green confirm mark and concise conclusion card on desk"),
        ("警告", "amber warning UI on screen, tense desk atmosphere"),
        ("终端", "developer terminal window with readable commands"),
        ("引用", "quoted pain-point text on a dark card, moody lighting"),
    )
    cinematic = ""
    for key, eng in translations:
        if key in src:
            cinematic = eng
            break
    if not cinematic:
        cinematic = (
            f"vertical social video scene illustrating: {src[:40] or title}"
        )
    role_hint = _ROLE_SHOT_HINTS.get((role or "").lower(), "cinematic desk analysis shot")
    # Pull a concrete noun phrase from narration (skip densify filler)
    beat = ""
    for chunk in re.split(r"[。！？；\n]", narration or ""):
        c = chunk.strip()
        if c and "这里补一句可执行细节" not in c:
            beat = c[:60]
            break
    return f"{cinematic}; {role_hint}; topic cue: {on_screen or title}; beat: {beat}"


def ensure_visual_board_shot(
    visual: str,
    *,
    role: str = "",
    on_screen: str = "",
    title: str = "",
    narration: str = "",
) -> str:
    """Guarantee `板式｜镜头` so L0 footnotes and L1 Agnes both get content."""
    board, shot = _split_visual_board_shot(visual)
    board = (board or on_screen or title or "要点卡").strip()[:40]
    if len(shot) >= 8:
        return f"{board}｜{shot}"
    filled = _board_to_cinematic_shot(
        visual=board,
        role=role,
        on_screen=on_screen,
        title=title,
        narration=narration,
    )
    return f"{board}｜{filled}"[:120]


def _agnes_scene_prompt(
    *,
    title: str,
    meta: dict[str, Any],
    narration: str,
    bg_theme: str,
    cover_hook: str,
) -> str:
    visual = (meta.get("visual") or "").strip()
    on_screen = (meta.get("on_screen") or cover_hook or title or "").strip()
    mood = (meta.get("mood") or "").strip()
    role = (meta.get("role") or "value").strip().lower()
    theme_label = (BG_THEMES.get(bg_theme) or {}).get("label") or bg_theme
    shot = _board_to_cinematic_shot(
        visual=visual,
        role=role,
        on_screen=on_screen,
        title=title,
        narration=narration,
    )
    parts = [
        shot,
        f"role={role}",
        f"key message: {on_screen}" if on_screen else "",
        f"mood: {mood}" if mood else "",
        f"color grade inspired by {theme_label}",
        "vertical 9:16, cinematic B-roll matching the spoken tip, no watermark, no logo",
        "no unreadable random glyphs; prefer real desks, screens, charts, hands",
        "smooth camera motion, high quality",
    ]
    text = ", ".join(p for p in parts if p)
    # More of the narration beat (was 80 — too short to stay on-topic)
    if narration:
        clean = re.sub(r"这里补一句可执行细节[^。]*。?", "", narration)
        text += f". Narration intent: {clean[:160]}"
    return text[:1400]


def missing_scene_clips(project_id: str, n_scenes: int) -> list[int]:
    """1-based scene indexes whose scene_{i}.mp4 is missing on disk."""
    root = project_dir(project_id)
    n = max(0, int(n_scenes or 0))
    return [i for i in range(1, n + 1) if not (root / f"scene_{i}.mp4").is_file()]


async def remux_project_final(project_id: str, n_scenes: int) -> tuple[str, float]:
    """Concat existing scene_*.mp4 into final.mp4. Raises if any clip missing."""
    root = project_dir(project_id)
    missing = missing_scene_clips(project_id, n_scenes)
    if missing:
        names = ", ".join(f"scene_{i}.mp4" for i in missing)
        raise RuntimeError(
            f"缺少分镜片段：{names}。请先完整渲染一次，或重渲缺失镜"
        )
    clips: list[Path] = []
    total = 0.0
    for i in range(1, n_scenes + 1):
        clip = root / f"scene_{i}.mp4"
        clips.append(clip)
        # Prefer ffprobe duration; fall back later
        try:
            r = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(clip),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            total += float((r.stdout or "0").strip() or 0)
        except Exception:  # noqa: BLE001
            pass
    final = root / "final.mp4"
    await concat_clips(clips, final)
    if total <= 0:
        total = float(n_scenes)
    return str(final), total


async def render_one_scene(
    *,
    project_id: str,
    scene: dict[str, Any],
    idx: int,
    total_scenes: int,
    title: str,
    voice: str = "zh-CN-XiaoxiaoNeural",
    cover_hook: str = "",
    hashtags: Optional[list[str]] = None,
    cta: str = "",
    bg_theme: str = "night",
    motion: str = "kenburns",
    render_mode: str = "local",
    refresh: str = "all",
) -> dict[str, Any]:
    """Render a single scene clip. refresh: all | tts+clip | clip | tts.

    Returns updated fields for DB persist (tts_path, image_path meta, duration).
    """
    root = project_dir(project_id)
    bg_theme = bg_theme if bg_theme in BG_THEMES else "night"
    motion = motion if motion in MOTIONS else "kenburns"
    render_mode = render_mode if render_mode in ("local", "agnes-video") else "local"
    refresh = (refresh or "all").lower()

    narration = scene.get("content") or scene.get("narration") or ""
    raw_visual = scene.get("image_path") or scene.get("visual") or ""
    meta = unpack_scene_meta(str(raw_visual))
    if not meta.get("on_screen") and scene.get("on_screen"):
        meta["on_screen"] = scene.get("on_screen") or ""
    if not meta.get("role") and scene.get("role"):
        meta["role"] = scene.get("role") or "value"

    audio = root / f"scene_{idx}.mp3"
    image = root / f"scene_{idx}.png"
    clip = root / f"scene_{idx}.mp4"
    agnes_raw = root / f"scene_{idx}_agnes.mp4"

    need_tts = refresh in ("all", "tts", "tts+clip") or not audio.is_file()
    # Visual regenerate unless narration-only remux of existing Agnes plate
    force_visual = refresh in ("all", "clip", "tts+clip")
    reuse_agnes = (
        render_mode == "agnes-video"
        and refresh == "tts"
        and agnes_raw.is_file()
    )
    need_agnes_gen = render_mode == "agnes-video" and not reuse_agnes and (
        force_visual or refresh == "all" or not agnes_raw.is_file()
    )

    if need_tts:
        dur = await synthesize_tts(narration, audio, voice=voice)
    else:
        dur = _audio_duration(audio) if audio.is_file() else 1.0

    role = meta.get("role") or scene.get("role") or "value"

    if render_mode == "agnes-video":
        from cn_social_agent.video.agnes_client import AgnesVideoClient

        if not AgnesVideoClient.configured():
            raise RuntimeError("Agnes Video 未配置：请设置 AGNES_API_KEY")
        agnes = AgnesVideoClient()
        if need_agnes_gen:
            prompt = _agnes_scene_prompt(
                title=title,
                meta=meta,
                narration=narration,
                bg_theme=bg_theme,
                cover_hook=cover_hook or title,
            )
            await agnes.generate_to_file(
                prompt,
                agnes_raw,
                width=768,
                height=1344,
                num_frames=121,
                frame_rate=24,
            )
        if not agnes_raw.is_file():
            raise RuntimeError("Agnes 画面不存在，请用 refresh=all 重渲此镜")
        render_scene_image(
            image,
            title=title,
            cover_hook=cover_hook or title,
            visual=meta.get("visual") or "",
            narration=narration,
            on_screen=meta.get("on_screen") or "",
            role=role,
            mood=meta.get("mood") or "",
            scene_num=idx,
            total=total_scenes,
            hashtags=hashtags,
            cta=cta,
            bg_theme=bg_theme,
        )
        await mux_video_audio(
            agnes_raw,
            audio,
            clip,
            dur,
            overlay_text=meta.get("on_screen") or cover_hook or "",
        )
    else:
        scene_motion = motion
        if motion == "kenburns":
            scene_motion = _ROLE_MOTION.get(str(role).lower(), "kenburns")
        card_kwargs = dict(
            title=title,
            cover_hook=cover_hook or title,
            visual=meta.get("visual") or "",
            narration=narration,
            on_screen=meta.get("on_screen") or "",
            role=role,
            mood=meta.get("mood") or "",
            scene_num=idx,
            total=total_scenes,
            hashtags=hashtags,
            cta=cta,
            bg_theme=bg_theme,
        )
        n_keys = max(6, min(10, int(round(dur * 2.2))))
        keys = write_scene_keyframes(
            root / f"scene_{idx}_keys", n_keys=n_keys, **card_kwargs
        )
        shutil.copyfile(keys[-1], image)
        await render_scene_clip(
            image,
            audio,
            clip,
            dur,
            motion=scene_motion,
            role=str(role),
            keyframes=keys,
        )

    meta["scene_render_mode"] = render_mode
    packed = scene_meta_for_persist(meta, poster=image)
    return {
        "tts_path": str(audio),
        "image_path": packed,
        "tts_duration_seconds": dur,
        "clip_path": str(clip),
        "meta": meta,
    }


async def render_project(
    *,
    project_id: str,
    title: str,
    scenes: list[dict[str, Any]],
    voice: str = "zh-CN-XiaoxiaoNeural",
    cover_hook: str = "",
    hashtags: Optional[list[str]] = None,
    cta: str = "",
    bg_theme: str = "night",
    motion: str = "kenburns",
    render_mode: str = "local",
    on_progress: Optional[Any] = None,
) -> tuple[str, float]:
    """Render all scenes; return (output_path, total_seconds)."""
    root = project_dir(project_id)
    clips: list[Path] = []
    total = 0.0
    n = len(scenes)
    bg_theme = bg_theme if bg_theme in BG_THEMES else "night"
    motion = motion if motion in MOTIONS else "kenburns"
    render_mode = render_mode if render_mode in ("local", "agnes-video") else "local"

    if render_mode == "agnes-video":
        from cn_social_agent.video.agnes_client import AgnesVideoClient

        if not AgnesVideoClient.configured():
            raise RuntimeError("Agnes Video 未配置：请设置 AGNES_API_KEY")

    for idx, scene in enumerate(scenes, start=1):
        if on_progress:
            await on_progress(idx, n, f"scene {idx}/{n} ({render_mode})")
        result = await render_one_scene(
            project_id=project_id,
            scene=scene,
            idx=idx,
            total_scenes=n,
            title=title,
            voice=voice,
            cover_hook=cover_hook,
            hashtags=hashtags,
            cta=cta,
            bg_theme=bg_theme,
            motion=motion,
            render_mode=render_mode,
            refresh="all",
        )
        scene["tts_path"] = result["tts_path"]
        scene["image_path"] = result["image_path"]
        scene["tts_duration_seconds"] = result["tts_duration_seconds"]
        clips.append(Path(result["clip_path"]))
        total += float(result["tts_duration_seconds"] or 0)

    final = root / "final.mp4"
    await concat_clips(clips, final)
    return str(final), total
