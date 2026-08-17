"""Produce-intent detection for Lead Agent modes."""

from __future__ import annotations

import re
from typing import Any

# Explicit production intent only. Hotspot / URL / atlas research stay in simple.
PRODUCE_HINTS = re.compile(
    r"("
    r"短视频|口播|做片|分镜|成片|草稿|抖音|视频号|小红书|"
    r"做成|拍一条|讲清|入门讲解|对比选型|深度分析|"
    r"讲解演示|网页演示|演示稿|OBS|"
    r"知识卡片|知识点卡片|岗位卡片|能力图谱|"
    r"intro|compare|deep_analysis|propose|L0|L1|presentation"
    r")",
    re.I,
)

STEP_DEFS = (
    ("topic", "选题"),
    ("angle", "类型"),
    ("brief", "要素"),
    ("script", "分镜"),
    ("l0", "草稿"),
    ("l1", "成片"),
)

RESEARCH_TOOLS = frozenset(
    {
        "now",
        "http_get",
        "fetch_url_text",
        "scan_hotspot_board",
        "github_rising_repos",
        "github_repo_insight",
        "population_census_lookup",
        "open_population_atlas",
        "lookup_topic_assets",
    }
)

PRODUCE_TOOLS = frozenset(
    {
        "list_video_styles",
        "clarify_brief",
        "propose_short_video",
        "present_video_artifact",
        "handoff_hotspot",
        "propose_presentation",
        "draft_presentation_content",
        "confirm_checkpoint",
        "scaffold_presentation",
        "build_chapter",
        "synthesize_narration_audio",
        "presentation_preview_url",
        "propose_knowledge_cards",
        "scan_knowledge_cards",
        "present_knowledge_card",
        "lookup_topic_assets",
        "write_todos",
    }
)


def last_user_text(messages: list[dict[str, Any]]) -> str:
    for m in reversed(messages or []):
        if m.get("role") == "user" and (m.get("content") or "").strip():
            return str(m.get("content") or "")
    return ""


def detect_mode(
    messages: list[dict[str, Any]],
    *,
    agent_state: dict[str, Any] | None = None,
    brief: str = "",
) -> str:
    """Return 'produce' or 'simple'."""
    state = agent_state or {}
    if state.get("active_project_id") or state.get("mode") == "produce":
        return "produce"
    if (brief or "").strip():
        return "produce"
    text = last_user_text(messages)
    if PRODUCE_HINTS.search(text or ""):
        return "produce"
    # Sticky: prior tool_calls in history mentioning propose/present
    for m in reversed(messages or []):
        tcs = m.get("tool_calls") or []
        if isinstance(tcs, list):
            for tc in tcs:
                name = (tc.get("name") if isinstance(tc, dict) else "") or ""
                if name in (
                    "propose_short_video",
                    "present_video_artifact",
                    "clarify_brief",
                    "write_todos",
                    "propose_knowledge_cards",
                    "scan_knowledge_cards",
                    "present_knowledge_card",
                ):
                    return "produce"
    return "simple"


def tools_for_mode(mode: str) -> frozenset[str]:
    if mode == "produce":
        return RESEARCH_TOOLS | PRODUCE_TOOLS
    return RESEARCH_TOOLS
