"""Internal usage metering for FDE cost visibility (JSONL, no billing)."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

# Event kinds used in weekly reports
KIND_L0_RENDER = "l0_render"
KIND_L1_RENDER = "l1_render"
KIND_SCENE_RENDER = "scene_render"
KIND_CARD_COMPOSE = "card_compose"
KIND_CARD_PUBLISH = "card_publish"
KIND_VIDEO_PUBLISH = "video_publish"
KIND_LLM_CHAT = "llm_chat"

_DEFAULT_COSTS_CNY: dict[str, float] = {
    KIND_L0_RENDER: 0.05,  # per scene equivalent; scaled by scenes
    KIND_L1_RENDER: 2.5,  # per scene
    KIND_SCENE_RENDER: 0.0,  # use delivery_level instead
    KIND_CARD_COMPOSE: 0.3,
    KIND_CARD_PUBLISH: 0.0,
    KIND_VIDEO_PUBLISH: 0.0,
    KIND_LLM_CHAT: 0.02,
}

_lock = threading.Lock()


def _project_root() -> Path:
    # usage/meter.py → usage → cn_social_agent → src → repo root
    return Path(__file__).resolve().parents[3]


def usage_log_path() -> Path:
    raw = (os.getenv("USAGE_LOG_PATH") or "").strip()
    if raw:
        return Path(raw)
    customer = (os.getenv("USAGE_CUSTOMER_ID") or "default").strip() or "default"
    return _project_root() / "data" / "usage" / customer / "events.jsonl"


def customer_id() -> str:
    return (os.getenv("USAGE_CUSTOMER_ID") or "default").strip() or "default"


def _env_cost(name: str, default: float) -> float:
    try:
        return float(os.getenv(name) or default)
    except ValueError:
        return default


def unit_costs_cny() -> dict[str, float]:
    """Unit costs in CNY; overridable via env for FDE quoting."""
    return {
        KIND_L0_RENDER: _env_cost("USAGE_COST_L0_SCENE", _DEFAULT_COSTS_CNY[KIND_L0_RENDER]),
        KIND_L1_RENDER: _env_cost("USAGE_COST_L1_SCENE", _DEFAULT_COSTS_CNY[KIND_L1_RENDER]),
        KIND_CARD_COMPOSE: _env_cost(
            "USAGE_COST_CARD_COMPOSE", _DEFAULT_COSTS_CNY[KIND_CARD_COMPOSE]
        ),
        KIND_LLM_CHAT: _env_cost("USAGE_COST_LLM_CHAT", _DEFAULT_COSTS_CNY[KIND_LLM_CHAT]),
        KIND_CARD_PUBLISH: _env_cost(
            "USAGE_COST_PUBLISH", _DEFAULT_COSTS_CNY[KIND_CARD_PUBLISH]
        ),
        KIND_VIDEO_PUBLISH: _env_cost(
            "USAGE_COST_PUBLISH", _DEFAULT_COSTS_CNY[KIND_VIDEO_PUBLISH]
        ),
        KIND_SCENE_RENDER: 0.0,
    }


def estimate_cost_cny(
    kind: str,
    *,
    scenes: int = 1,
    delivery_level: str = "",
) -> float:
    costs = unit_costs_cny()
    n = max(1, int(scenes or 1))
    level = (delivery_level or "").strip().lower()
    if kind == KIND_SCENE_RENDER:
        kind = KIND_L1_RENDER if level == "l1" else KIND_L0_RENDER
    if kind in (KIND_L0_RENDER, KIND_L1_RENDER):
        return round(costs.get(kind, 0.0) * n, 4)
    return round(float(costs.get(kind, 0.0)), 4)


def record_event(
    kind: str,
    *,
    user_id: str = "",
    project_id: str = "",
    scenes: int = 0,
    delivery_level: str = "",
    status: str = "ok",
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Append one JSONL usage event. Never raises to callers."""
    try:
        event: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "customer_id": customer_id(),
            "kind": kind,
            "user_id": user_id or "",
            "project_id": project_id or "",
            "scenes": int(scenes or 0),
            "delivery_level": (delivery_level or "").strip().lower(),
            "status": status or "ok",
            "cost_cny_est": estimate_cost_cny(
                kind, scenes=scenes or 1, delivery_level=delivery_level
            ),
            "meta": meta or {},
        }
        path = usage_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False)
        with _lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        return event
    except Exception:  # noqa: BLE001
        return {}


def _parse_ts(raw: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:  # noqa: BLE001
        return None


def load_events(
    *,
    days: int = 7,
    path: Optional[Path] = None,
    since: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    log = path or usage_log_path()
    if not log.exists():
        return []
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))
    out: list[dict[str, Any]] = []
    with log.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            ts = _parse_ts(str(row.get("ts") or ""))
            if ts is None or ts < since:
                continue
            out.append(row)
    return out


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    by_status: dict[str, int] = {}
    l0_scenes = 0
    l1_scenes = 0
    cost = 0.0
    cid = customer_id()
    for ev in events:
        if ev.get("customer_id"):
            cid = str(ev.get("customer_id"))
        kind = str(ev.get("kind") or "unknown")
        by_kind[kind] = by_kind.get(kind, 0) + 1
        st = str(ev.get("status") or "ok")
        by_status[st] = by_status.get(st, 0) + 1
        scenes = int(ev.get("scenes") or 0)
        level = str(ev.get("delivery_level") or "")
        if kind == KIND_L1_RENDER or (kind == KIND_SCENE_RENDER and level == "l1"):
            l1_scenes += max(scenes, 1)
        elif kind == KIND_L0_RENDER or (kind == KIND_SCENE_RENDER and level != "l1"):
            l0_scenes += max(scenes, 1)
        try:
            cost += float(ev.get("cost_cny_est") or 0)
        except (TypeError, ValueError):
            pass
    return {
        "customer_id": cid,
        "event_count": len(events),
        "by_kind": by_kind,
        "by_status": by_status,
        "l0_scene_units": l0_scenes,
        "l1_scene_units": l1_scenes,
        "estimated_cost_cny": round(cost, 2),
        "unit_costs_cny": unit_costs_cny(),
    }


def weekly_summary(*, days: int = 7, path: Optional[Path] = None) -> dict[str, Any]:
    events = load_events(days=days, path=path)
    summary = summarize_events(events)
    summary["days"] = days
    summary["log_path"] = str(path or usage_log_path())
    return summary


def format_weekly_report(summary: dict[str, Any]) -> str:
    lines = [
        f"# Usage weekly report — {summary.get('customer_id')}",
        f"Window: last {summary.get('days')} day(s)",
        f"Log: {summary.get('log_path')}",
        "",
        f"Events: {summary.get('event_count')}",
        f"L0 scene units: {summary.get('l0_scene_units')}",
        f"L1 scene units: {summary.get('l1_scene_units')}",
        f"Estimated cost (CNY): {summary.get('estimated_cost_cny')}",
        "",
        "## By kind",
    ]
    for k, v in sorted((summary.get("by_kind") or {}).items()):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## By status")
    for k, v in sorted((summary.get("by_status") or {}).items()):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Unit costs (CNY)")
    for k, v in sorted((summary.get("unit_costs_cny") or {}).items()):
        lines.append(f"- {k}: {v}")
    return "\n".join(lines) + "\n"
