"""User preference memory for Agent + video workshop (lightweight DeerFlow-style)."""

from __future__ import annotations

from typing import Any

DEFAULT_PREFS: dict[str, Any] = {
    "default_audience": "",
    "default_voice": "zh-CN-XiaoxiaoNeural",
    "default_content_angle": "intro",
    "default_platform": "抖音",
    "default_video_track": "",
    "default_pres_aspect": "9:16",
    "default_pres_theme": "talent-map",
    "recent_topics": [],
    "recent_recipes": [],
    "llm_mode": "",
    "llm_model": "",
    "llm_route": "smart",
    "llm_model_fast": "",
    "llm_model_strong": "",
    "connectors_enabled": {},
    "hotspot_sources_enabled": {},
    "automations_enabled": {},
    "automation_last_run": {},
    "automation_runs": [],
    "canvas_scratch": {},
}

_ALLOWED_ANGLES = frozenset({"intro", "compare", "deep_analysis", "idea", "general"})
_ALLOWED_LLM_MODES = frozenset({"agnes", "ollama", "minimax", "insforge", "mock"})
_ALLOWED_LLM_ROUTES = frozenset({"smart", "fixed"})
_VOICE_DEFAULTS = frozenset({"zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"})
_ALLOWED_ASPECTS = frozenset({"9:16", "16:9"})
_ALLOWED_THEMES = frozenset({"talent-map", "paper-press", "desk", "terminal-green"})


def normalize_video_track(raw: Any) -> str:
    t = str(raw or "").strip().lower()
    if t in ("presentation", "讲解", "讲解演示", "web-presentation"):
        return "presentation"
    if t in ("koubo", "口播", "口播短视频", "short", "short_video"):
        return "koubo"
    return ""


def normalize_prefs(raw: dict[str, Any] | None) -> dict[str, Any]:
    src = raw or {}
    angle = (src.get("default_content_angle") or DEFAULT_PREFS["default_content_angle"]).strip()
    if angle in ("idea", "general"):
        angle = "intro"
    if angle not in _ALLOWED_ANGLES:
        angle = "intro"
    voice = (src.get("default_voice") or DEFAULT_PREFS["default_voice"]).strip()
    if voice not in _VOICE_DEFAULTS:
        # allow custom neural names but fall back if empty
        voice = voice or DEFAULT_PREFS["default_voice"]
    topics = src.get("recent_topics") or []
    if isinstance(topics, str):
        try:
            import json

            topics = json.loads(topics)
        except Exception:  # noqa: BLE001
            topics = [topics] if topics.strip() else []
    if not isinstance(topics, list):
        topics = []
    clean_topics: list[str] = []
    for t in topics:
        s = str(t or "").strip()
        if s and s not in clean_topics:
            clean_topics.append(s[:80])
        if len(clean_topics) >= 3:
            break
    recipes_raw = src.get("recent_recipes") or []
    if isinstance(recipes_raw, str):
        try:
            import json

            recipes_raw = json.loads(recipes_raw)
        except Exception:  # noqa: BLE001
            recipes_raw = []
    if not isinstance(recipes_raw, list):
        recipes_raw = []
    clean_recipes: list[dict[str, str]] = []
    seen_r: set[str] = set()
    for r in recipes_raw:
        if not isinstance(r, dict):
            continue
        angle = str(r.get("content_angle") or "").strip()
        if angle in ("idea", "general"):
            angle = "intro"
        if angle not in _ALLOWED_ANGLES:
            continue
        aud = str(r.get("audience") or "").strip()[:80]
        scene = str(r.get("scene_setting") or "").strip()[:80]
        sig = f"{angle}|{aud}|{scene}"
        if sig in seen_r:
            continue
        seen_r.add(sig)
        clean_recipes.append(
            {"content_angle": angle, "audience": aud, "scene_setting": scene}
        )
        if len(clean_recipes) >= 5:
            break
    llm_mode = str(src.get("llm_mode") or "").strip().lower()
    if llm_mode and llm_mode not in _ALLOWED_LLM_MODES:
        llm_mode = ""
    llm_model = str(src.get("llm_model") or "").strip()[:120]
    llm_route = str(src.get("llm_route") or DEFAULT_PREFS["llm_route"]).strip().lower()
    if llm_route not in _ALLOWED_LLM_ROUTES:
        llm_route = "smart"
    llm_model_fast = str(src.get("llm_model_fast") or "").strip()[:120]
    llm_model_strong = str(src.get("llm_model_strong") or "").strip()[:120]
    track = normalize_video_track(src.get("default_video_track"))
    aspect = str(src.get("default_pres_aspect") or DEFAULT_PREFS["default_pres_aspect"]).strip()
    if aspect not in _ALLOWED_ASPECTS:
        aspect = "9:16"
    theme = str(src.get("default_pres_theme") or DEFAULT_PREFS["default_pres_theme"]).strip()
    if theme not in _ALLOWED_THEMES:
        theme = "talent-map"
    from cn_social_agent.content.connectors import normalize_connector_prefs
    from cn_social_agent.content.automations import normalize_automation_prefs

    conn = normalize_connector_prefs(src)
    auto = normalize_automation_prefs(src)
    scratch_raw = src.get("canvas_scratch")
    if not isinstance(scratch_raw, dict):
        scratch_raw = {}
    scratch_nodes = scratch_raw.get("nodes")
    scratch = {
        "nodes": [n for n in scratch_nodes if isinstance(n, dict)][:200]
        if isinstance(scratch_nodes, list)
        else [],
        "updated_at": str(scratch_raw.get("updated_at") or ""),
    }
    return {
        "default_audience": str(src.get("default_audience") or "").strip()[:120],
        "default_voice": voice,
        "default_content_angle": angle,
        "default_platform": str(src.get("default_platform") or DEFAULT_PREFS["default_platform"]).strip()[
            :40
        ]
        or "抖音",
        "default_video_track": track,
        "default_pres_aspect": aspect,
        "default_pres_theme": theme,
        "recent_topics": clean_topics,
        "recent_recipes": clean_recipes,
        "llm_mode": llm_mode,
        "llm_model": llm_model,
        "llm_route": llm_route,
        "llm_model_fast": llm_model_fast,
        "llm_model_strong": llm_model_strong,
        "connectors_enabled": conn["connectors_enabled"],
        "hotspot_sources_enabled": conn["hotspot_sources_enabled"],
        "automations_enabled": auto["automations_enabled"],
        "automation_last_run": auto["automation_last_run"],
        "automation_runs": auto["automation_runs"],
        "canvas_scratch": scratch,
    }


def merge_prefs(current: dict[str, Any] | None, patch: dict[str, Any]) -> dict[str, Any]:
    base = normalize_prefs(current)
    data = {**base}
    for key in (
        "default_audience",
        "default_voice",
        "default_content_angle",
        "default_platform",
        "default_video_track",
        "default_pres_aspect",
        "default_pres_theme",
        "llm_mode",
        "llm_model",
        "llm_route",
        "llm_model_fast",
        "llm_model_strong",
    ):
        if key in patch and patch[key] is not None:
            data[key] = patch[key]
    if "recent_topics" in patch and patch["recent_topics"] is not None:
        data["recent_topics"] = patch["recent_topics"]
    if "recent_recipes" in patch and patch["recent_recipes"] is not None:
        data["recent_recipes"] = patch["recent_recipes"]
    topic = (patch.get("push_topic") or "").strip()
    if topic:
        topics = [topic[:80]] + [t for t in data["recent_topics"] if t != topic[:80]]
        data["recent_topics"] = topics[:3]
    recipe = patch.get("push_recipe")
    if isinstance(recipe, dict):
        angle = str(recipe.get("content_angle") or data["default_content_angle"] or "intro").strip()
        if angle in ("idea", "general"):
            angle = "intro"
        if angle in _ALLOWED_ANGLES:
            item = {
                "content_angle": angle,
                "audience": str(recipe.get("audience") or "").strip()[:80],
                "scene_setting": str(recipe.get("scene_setting") or "").strip()[:80],
            }
            sig = f"{item['content_angle']}|{item['audience']}|{item['scene_setting']}"
            rest = [
                r
                for r in data.get("recent_recipes") or []
                if isinstance(r, dict)
                and f"{r.get('content_angle')}|{r.get('audience')}|{r.get('scene_setting')}" != sig
            ]
            data["recent_recipes"] = [item] + rest
    if "connectors_enabled" in patch and isinstance(patch["connectors_enabled"], dict):
        data["connectors_enabled"] = {
            **(data.get("connectors_enabled") or {}),
            **{str(k): bool(v) for k, v in patch["connectors_enabled"].items()},
        }
    if "hotspot_sources_enabled" in patch and isinstance(patch["hotspot_sources_enabled"], dict):
        data["hotspot_sources_enabled"] = {
            **(data.get("hotspot_sources_enabled") or {}),
            **{str(k): bool(v) for k, v in patch["hotspot_sources_enabled"].items()},
        }
    if "automations_enabled" in patch and isinstance(patch["automations_enabled"], dict):
        data["automations_enabled"] = {
            **(data.get("automations_enabled") or {}),
            **{str(k): bool(v) for k, v in patch["automations_enabled"].items()},
        }
    if "automation_last_run" in patch and isinstance(patch["automation_last_run"], dict):
        data["automation_last_run"] = {
            **(data.get("automation_last_run") or {}),
            **{str(k): str(v)[:40] for k, v in patch["automation_last_run"].items()},
        }
    if "automation_runs" in patch and isinstance(patch["automation_runs"], list):
        data["automation_runs"] = [x for x in patch["automation_runs"] if isinstance(x, dict)][:30]
    if "canvas_scratch" in patch and isinstance(patch["canvas_scratch"], dict):
        data["canvas_scratch"] = patch["canvas_scratch"]
    return normalize_prefs(data)


def prefs_prompt_block(prefs: dict[str, Any]) -> str:
    p = normalize_prefs(prefs)
    lines = ["# User preferences (remember across sessions)", ""]
    if p["default_audience"]:
        lines.append(f"- Default audience: {p['default_audience']}")
    if p["default_platform"]:
        lines.append(f"- Default platform: {p['default_platform']}")
    if p["default_video_track"] == "presentation":
        lines.append("- Default video track: 讲解演示 (presentation)")
        lines.append(f"- Default presentation aspect: {p['default_pres_aspect']}")
        lines.append(f"- Default presentation theme: {p['default_pres_theme']}")
    elif p["default_video_track"] == "koubo":
        lines.append("- Default video track: 口播短视频 (koubo)")
    if p["default_content_angle"]:
        lines.append(f"- Preferred video type: {p['default_content_angle']}")
    if p["default_voice"]:
        lines.append(f"- Preferred voice: {p['default_voice']}")
    if p["recent_topics"]:
        lines.append("- Recent topics: " + "；".join(p["recent_topics"]))
    if len(lines) <= 2:
        lines.append("- (empty — learn audience/scene from the user)")
    lines.append("")
    lines.append(
        "When proposing a video, first confirm 口播 vs 讲解演示 (reuse default_video_track if set). "
        "Reuse audience/platform defaults unless the user overrides them."
    )
    return "\n".join(lines)


def production_brief_from_messages(history: list[dict[str, Any]]) -> str:
    """Extract a compact production brief from recent tool_calls for long chats."""
    brief: dict[str, str] = {}
    for m in reversed(history or []):
        for tc in m.get("tool_calls") or []:
            name = tc.get("name") or ""
            args = tc.get("arguments") or {}
            result = tc.get("result") or {}
            data = result.get("data") if isinstance(result, dict) else {}
            if not isinstance(data, dict):
                data = {}
            if not isinstance(args, dict):
                args = {}
            merged = {**args, **data}
            if name in (
                "propose_short_video",
                "clarify_brief",
                "short_video_project",
                "present_video_artifact",
                "propose_presentation",
                "draft_presentation_content",
            ):
                for key in (
                    "topic",
                    "audience",
                    "scene_setting",
                    "platform",
                    "cta",
                    "project_id",
                    "video_track",
                    "aspect",
                    "theme",
                ):
                    val = (merged.get(key) or "").strip() if isinstance(merged.get(key), str) else ""
                    if val and key not in brief:
                        brief[key] = val[:200]
        if len(brief) >= 4:
            break
    if not brief:
        return ""
    lines = ["# Current production brief (from this session)", ""]
    for key, label in (
        ("topic", "Topic"),
        ("audience", "Audience"),
        ("scene_setting", "Scene"),
        ("platform", "Platform"),
        ("cta", "CTA"),
        ("project_id", "Project"),
    ):
        if brief.get(key):
            lines.append(f"- {label}: {brief[key]}")
    return "\n".join(lines)


def trim_messages_for_context(
    messages: list[dict[str, Any]], *, max_messages: int = 24
) -> list[dict[str, Any]]:
    if len(messages) <= max_messages:
        return messages
    return messages[-max_messages:]
