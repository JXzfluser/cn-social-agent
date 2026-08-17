"""Session agent_state helpers (DeerFlow-lite todos)."""

from __future__ import annotations

import json
from typing import Any

from cn_social_agent.agent.mode import STEP_DEFS


def empty_agent_state(*, mode: str = "simple") -> dict[str, Any]:
    return {
        "mode": mode,
        # Video pipeline todos only when producing — avoid Agent UI showing 选题/类型…
        "todos": default_todos() if mode == "produce" else [],
        "active_project_id": None,
        "last_clarify": None,
        "needs_present": False,
    }


def default_todos() -> list[dict[str, str]]:
    return [
        {"id": sid, "label": label, "status": "pending", "detail": ""}
        for sid, label in STEP_DEFS
    ]


def normalize_agent_state(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str) and raw.strip():
        try:
            raw = json.loads(raw)
        except Exception:  # noqa: BLE001
            raw = {}
    if not isinstance(raw, dict):
        raw = {}
    base = empty_agent_state(mode=str(raw.get("mode") or "simple"))
    todos_in = raw.get("todos")
    if isinstance(todos_in, list) and todos_in:
        by_id = {str(t.get("id")): t for t in todos_in if isinstance(t, dict)}
        todos = []
        for sid, label in STEP_DEFS:
            src = by_id.get(sid) or {}
            st = str(src.get("status") or "pending")
            if st not in ("pending", "active", "done", "blocked", "failed"):
                st = "pending"
            todos.append(
                {
                    "id": sid,
                    "label": str(src.get("label") or label),
                    "status": st,
                    "detail": str(src.get("detail") or "")[:80],
                }
            )
        base["todos"] = todos
    base["mode"] = str(raw.get("mode") or base["mode"])
    # Drop inert video plan chrome when still in research mode with no project
    if base["mode"] != "produce" and not raw.get("active_project_id"):
        progressed = any(
            (t.get("status") or "pending") != "pending" or (t.get("detail") or "").strip()
            for t in (base.get("todos") or [])
        )
        if not progressed:
            base["todos"] = []
    pid = raw.get("active_project_id")
    base["active_project_id"] = str(pid).strip() if pid else None
    base["last_clarify"] = raw.get("last_clarify") if isinstance(raw.get("last_clarify"), dict) else None
    base["needs_present"] = bool(raw.get("needs_present"))
    return base


def encode_agent_state(state: dict[str, Any]) -> str:
    return json.dumps(normalize_agent_state(state), ensure_ascii=False)


def plan_prompt_block(state: dict[str, Any]) -> str:
    s = normalize_agent_state(state)
    if s.get("mode") != "produce":
        return ""
    lines = ["# Active produce plan"]
    if s.get("active_project_id"):
        lines.append(f"active_project_id: {s['active_project_id']}")
    for t in s.get("todos") or []:
        lines.append(f"- [{t['status']}] {t['label']}" + (f" · {t['detail']}" if t.get("detail") else ""))
    if s.get("needs_present"):
        lines.append("needs_present: true — call present_video_artifact when project_id exists")
    text = "\n".join(lines)
    return text[:400]


def apply_write_todos(
    state: dict[str, Any],
    todos: list[dict[str, Any]] | None = None,
    *,
    active_project_id: str | None = None,
) -> dict[str, Any]:
    out = normalize_agent_state(state)
    out["mode"] = "produce"
    if active_project_id is not None:
        out["active_project_id"] = (active_project_id or "").strip() or None
    if todos:
        by_id = {str(t.get("id")): t for t in todos if isinstance(t, dict)}
        merged = []
        for sid, label in STEP_DEFS:
            src = by_id.get(sid) or {}
            prev = next((x for x in out["todos"] if x["id"] == sid), {})
            st = str(src.get("status") or prev.get("status") or "pending")
            if st not in ("pending", "active", "done", "blocked", "failed"):
                st = "pending"
            merged.append(
                {
                    "id": sid,
                    "label": str(src.get("label") or prev.get("label") or label),
                    "status": st,
                    "detail": str(src.get("detail") or prev.get("detail") or "")[:80],
                }
            )
        out["todos"] = merged
    return out


def sync_todos_from_production_plan(
    state: dict[str, Any], production_plan: dict[str, Any] | None
) -> dict[str, Any]:
    """When a video project exists, production_plan is the source of truth."""
    out = normalize_agent_state(state)
    if not production_plan or not isinstance(production_plan.get("steps"), list):
        return out
    out["mode"] = "produce"
    steps = {s.get("id"): s for s in production_plan["steps"] if isinstance(s, dict)}
    todos = []
    for sid, label in STEP_DEFS:
        step = steps.get(sid) or {}
        st = str(step.get("status") or "pending")
        if st not in ("pending", "active", "done", "blocked", "failed"):
            st = "pending"
        todos.append(
            {
                "id": sid,
                "label": str(step.get("label") or label),
                "status": st,
                "detail": str(step.get("detail") or "")[:80],
            }
        )
    out["todos"] = todos
    return out


def bump_todos_from_tools(state: dict[str, Any], tool_trace: list[dict[str, Any]]) -> dict[str, Any]:
    """Heuristic progress when no project yet."""
    out = normalize_agent_state(state)
    if out.get("active_project_id"):
        return out
    out["mode"] = "produce"

    def set_status(sid: str, status: str, detail: str = "") -> None:
        for t in out["todos"]:
            if t["id"] == sid:
                t["status"] = status
                if detail:
                    t["detail"] = detail[:80]
                break

    for tc in tool_trace or []:
        name = tc.get("name") or ""
        result = (tc.get("result") or {}).get("data") if isinstance(tc.get("result"), dict) else None
        if not isinstance(result, dict):
            result = tc.get("result") if isinstance(tc.get("result"), dict) else {}
        data = result if isinstance(result, dict) else {}
        # unwrap ToolResult shape
        if "data" in data and isinstance(data.get("data"), dict) and "success" in data:
            data = data["data"]

        if name == "clarify_brief":
            set_status("brief", "active", "澄清中")
            out["last_clarify"] = {
                "question": data.get("question") or "",
                "need": data.get("need") or [],
                "topic": data.get("topic") or "",
            }
        elif name == "propose_short_video":
            topic = str(data.get("topic") or "")
            if topic:
                set_status("topic", "done", topic[:40])
            if data.get("ready"):
                set_status("brief", "done")
                set_status("angle", "active")
                set_status("script", "active", "待生成分镜")
            else:
                set_status("brief", "active", "缺受众/场景")
        elif name == "present_video_artifact":
            pid = str(data.get("project_id") or "")
            if pid:
                out["active_project_id"] = pid
                out["needs_present"] = False
                set_status("script", "active", "已呈递项目")
        elif name == "write_todos":
            pass
    return out
