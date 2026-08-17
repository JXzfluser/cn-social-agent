"""Lead Agent middleware: clarify hard-gate, present close, tool filtering."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from cn_social_agent.agent.mode import tools_for_mode
from cn_social_agent.agent.state import (
    apply_write_todos,
    bump_todos_from_tools,
    normalize_agent_state,
)
from cn_social_agent.tools.builtin import tool_clarify_brief, tool_present_video_artifact
from cn_social_agent.tools.registry import ToolRegistry, ToolResult


_PRES_TOOLS = ("propose_presentation", "draft_presentation_content")


def _prefs_audience(prefs: dict[str, Any]) -> str:
    return str((prefs or {}).get("default_audience") or "").strip()


def _prefs_track(prefs: dict[str, Any]) -> str:
    from cn_social_agent.api.prefs import normalize_video_track

    return normalize_video_track((prefs or {}).get("default_video_track"))


@dataclass
class TurnContext:
    mode: str
    prefs: dict[str, Any] = field(default_factory=dict)
    agent_state: dict[str, Any] = field(default_factory=dict)
    tool_trace: list[dict[str, Any]] = field(default_factory=list)


def _unwrap_data(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    if "data" in payload and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


async def before_tool(
    name: str,
    args: dict[str, Any],
    ctx: TurnContext,
    tools: ToolRegistry,
) -> tuple[str, dict[str, Any], Optional[ToolResult]]:
    """Possibly rewrite or short-circuit a tool call.

    Returns (name, args, forced_result_or_None).
    """
    if name == "propose_short_video":
        audience = str(args.get("audience") or "").strip()
        scene = str(args.get("scene_setting") or "").strip()
        if not audience:
            audience = _prefs_audience(ctx.prefs)
            if audience:
                args = {**args, "audience": audience}

        if audience or scene:
            return name, {**args, "video_track": "koubo"}, None

        # Hard gate: force clarify instead of propose
        clarify_args = {
            "question": "还缺一项：这是口播短视频还是讲解演示？目标受众或具体使用场景？",
            "need": "track|audience|scene",
            "topic": str(args.get("topic") or ""),
            "audience": "",
            "scene_setting": "",
            "platform": str(args.get("platform") or ""),
            "video_track": _prefs_track(ctx.prefs) or "koubo",
        }
        data = await tool_clarify_brief(**clarify_args)
        data["blocked_propose"] = True
        data["hint"] = "已拦截 propose_short_video：请先选轨并补受众或场景"
        forced = ToolResult(success=True, data=data, error=None, execution_time=0.0)
        return "clarify_brief", clarify_args, forced

    if name in _PRES_TOOLS:
        audience = str(args.get("audience") or "").strip()
        if not audience:
            audience = _prefs_audience(ctx.prefs)
            if audience:
                args = {**args, "audience": audience}
        aspect = str(args.get("aspect") or "").strip()
        theme = str(args.get("theme") or "").strip()
        if not aspect:
            aspect = str((ctx.prefs or {}).get("default_pres_aspect") or "9:16")
            args = {**args, "aspect": aspect}
        if not theme:
            theme = str((ctx.prefs or {}).get("default_pres_theme") or "talent-map")
            args = {**args, "theme": theme}
        if audience:
            return name, {**args, "video_track": "presentation"}, None
        clarify_args = {
            "question": "讲解演示还缺目标受众。",
            "need": "audience",
            "topic": str(args.get("topic") or ""),
            "audience": "",
            "scene_setting": "",
            "platform": "",
            "video_track": "presentation",
            "aspect": aspect or "9:16",
            "theme": theme or "talent-map",
        }
        data = await tool_clarify_brief(**clarify_args)
        data["blocked_propose"] = True
        data["hint"] = f"已拦截 {name}：请先补受众"
        forced = ToolResult(success=True, data=data, error=None, execution_time=0.0)
        return "clarify_brief", clarify_args, forced

    return name, args, None


async def after_turn(ctx: TurnContext, tools: ToolRegistry) -> TurnContext:
    """Apply write_todos, present close + todo bump."""
    # Apply explicit write_todos first
    for tc in ctx.tool_trace:
        if tc.get("name") != "write_todos":
            continue
        data = _unwrap_data(tc.get("result") or {})
        ctx.agent_state = apply_write_todos(
            ctx.agent_state,
            data.get("todos") if isinstance(data.get("todos"), list) else None,
            active_project_id=str(data.get("active_project_id") or "") or None,
        )

    ctx.agent_state = bump_todos_from_tools(ctx.agent_state, ctx.tool_trace)

    presented = False
    ready_propose: dict[str, Any] | None = None
    for tc in ctx.tool_trace:
        name = tc.get("name") or ""
        data = _unwrap_data(tc.get("result") or {})
        if name == "present_video_artifact" and data.get("ok") and data.get("project_id"):
            presented = True
            ctx.agent_state["active_project_id"] = str(data["project_id"])
            ctx.agent_state["needs_present"] = False
        if name == "propose_short_video" and data.get("ready"):
            ready_propose = data

    # Auto-present if we already have a project id
    pid = ctx.agent_state.get("active_project_id")
    if ready_propose and not presented and pid:
        data = await tool_present_video_artifact(
            project_id=str(pid),
            topic=str(ready_propose.get("topic") or ""),
            title=str(ready_propose.get("topic") or ""),
            note="提议已就绪，请到短视频工坊完成草稿/成片",
        )
        result = ToolResult(success=True, data=data, error=None, execution_time=0.0)
        ctx.tool_trace.append(
            {
                "name": "present_video_artifact",
                "arguments": {"project_id": pid},
                "result": result.to_dict(),
                "auto": True,
            }
        )
        ctx.agent_state["needs_present"] = False
    elif ready_propose and not presented and not pid:
        ctx.agent_state["needs_present"] = True
        ctx.agent_state["mode"] = "produce"

    ctx.agent_state = normalize_agent_state(ctx.agent_state)
    return ctx


def filter_openai_tools(tools: ToolRegistry, mode: str) -> list[dict[str, Any]]:
    allowed = tools_for_mode(mode)
    return [
        t.openai_schema()
        for t in tools._tools.values()  # noqa: SLF001 — intentional filter access
        if t.name in allowed
    ]


def extract_clarify_from_trace(tool_trace: list[dict[str, Any]]) -> dict[str, Any] | None:
    for tc in reversed(tool_trace or []):
        if tc.get("name") != "clarify_brief":
            continue
        data = _unwrap_data(tc.get("result") or {})
        if data.get("clarify"):
            return data
    return None


def extract_artifacts_from_trace(tool_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    arts: list[dict[str, Any]] = []
    for tc in tool_trace or []:
        name = tc.get("name") or ""
        data = _unwrap_data(tc.get("result") or {})
        if name == "present_video_artifact" and data.get("project_id"):
            arts.append(
                {
                    "type": "video_project",
                    "project_id": data.get("project_id"),
                    "topic": data.get("topic") or "",
                    "title": data.get("title") or "",
                    "note": data.get("note") or "",
                }
            )
        if name == "propose_short_video" and data.get("ready"):
            arts.append(
                {
                    "type": "propose",
                    "topic": data.get("topic") or "",
                    "ready": True,
                }
            )
        if name in ("propose_presentation", "draft_presentation_content") and (
            data.get("propose_presentation")
            or data.get("presentation")
            or data.get("draft_presentation")
        ):
            arts.append(
                {
                    "type": "propose_presentation",
                    "topic": data.get("topic") or "",
                    "thesis": data.get("thesis") or "",
                    "draft": bool(data.get("draft_presentation")),
                }
            )
        if name == "propose_knowledge_cards" and data.get("propose_cards"):
            arts.append(
                {
                    "type": "propose_cards",
                    "roles": data.get("roles") or [],
                }
            )
        if name in ("present_knowledge_card", "scan_knowledge_cards") and (
            data.get("card_id") or data.get("scan_cards")
        ):
            arts.append(
                {
                    "type": "knowledge_cards",
                    "card_id": data.get("card_id") or "",
                    "roles": data.get("roles") or [],
                    "title": data.get("title") or "",
                }
            )
        if name in ("open_population_atlas", "population_census_lookup") and data.get(
            "open_atlas"
        ):
            city_val = data.get("city_name") or ""
            if not city_val:
                raw_city = data.get("city")
                if isinstance(raw_city, str):
                    city_val = raw_city
                elif isinstance(raw_city, dict):
                    city_val = str(raw_city.get("city") or "")
            prov_val = data.get("province_name") or ""
            if not prov_val:
                raw_prov = data.get("province")
                if isinstance(raw_prov, str):
                    prov_val = raw_prov
                elif isinstance(raw_prov, dict):
                    prov_val = str(raw_prov.get("province") or "")
            arts.append(
                {
                    "type": "population_atlas",
                    "url": data.get("url")
                    or data.get("atlas_url")
                    or "/static/population-atlas.html",
                    "province": prov_val,
                    "city": city_val,
                    "note": data.get("note") or "",
                }
            )
    return arts


def dump_forced_tool_message(call_id: str, name: str, result: ToolResult) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": json.dumps(result.to_dict(), ensure_ascii=False),
        "name": name,
    }
