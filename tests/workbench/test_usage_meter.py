"""Tests for internal usage metering."""

from __future__ import annotations

import json
from pathlib import Path

from cn_social_agent.usage.meter import (
    KIND_L0_RENDER,
    KIND_L1_RENDER,
    estimate_cost_cny,
    format_weekly_report,
    load_events,
    record_event,
    summarize_events,
    weekly_summary,
)


def test_estimate_l1_scales_with_scenes():
    assert estimate_cost_cny(KIND_L1_RENDER, scenes=4) == estimate_cost_cny(
        KIND_L1_RENDER, scenes=1
    ) * 4


def test_record_and_summarize(tmp_path: Path, monkeypatch):
    log = tmp_path / "events.jsonl"
    monkeypatch.setenv("USAGE_LOG_PATH", str(log))
    monkeypatch.setenv("USAGE_CUSTOMER_ID", "acme")
    monkeypatch.setenv("USAGE_COST_L1_SCENE", "2.0")
    monkeypatch.setenv("USAGE_COST_L0_SCENE", "0.1")

    record_event(
        KIND_L0_RENDER,
        user_id="u1",
        project_id="p1",
        scenes=8,
        delivery_level="l0",
        status="ok",
    )
    record_event(
        KIND_L1_RENDER,
        user_id="u1",
        project_id="p2",
        scenes=3,
        delivery_level="l1",
        status="ok",
    )
    record_event(
        KIND_L1_RENDER,
        user_id="u1",
        project_id="p3",
        scenes=2,
        delivery_level="l1",
        status="error",
    )

    assert log.exists()
    lines = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x]
    assert len(lines) == 3
    assert lines[0]["customer_id"] == "acme"

    summary = weekly_summary(days=7, path=log)
    assert summary["event_count"] == 3
    assert summary["l0_scene_units"] == 8
    assert summary["l1_scene_units"] == 5
    assert summary["estimated_cost_cny"] == round(0.1 * 8 + 2.0 * 3 + 2.0 * 2, 2)
    assert "L1 scene units" in format_weekly_report(summary)

    events = load_events(days=7, path=log)
    assert summarize_events(events)["by_status"].get("error") == 1
