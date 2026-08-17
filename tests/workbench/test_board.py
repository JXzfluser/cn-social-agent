"""Content Project board lanes."""

from __future__ import annotations

import pytest


def test_project_lane_mapping():
    from cn_social_agent.content.board import project_lane

    assert project_lane({"status": "candidate"}) == "candidate"
    assert project_lane({"status": "researching"}) == "active"
    assert project_lane({"status": "composing"}) == "active"
    assert project_lane({"status": "export_ready"}) == "export_ready"
    assert project_lane({"status": "done", "quality": {"export_ready": True}}) == "export_ready"
    assert project_lane({"status": "researching", "quality": {"export_ready": True}}) == "export_ready"
    assert project_lane({"status": "rejected"}) == "rejected"
    assert project_lane({"status": "researching", "quality": {"rejected": True}}) == "rejected"


def test_apply_lane_reject_requires_reason():
    from cn_social_agent.content.board import apply_lane_move

    with pytest.raises(ValueError):
        apply_lane_move({"status": "researching"}, "rejected", reason="")


def test_apply_lane_reject_and_reopen():
    from cn_social_agent.content.board import apply_lane_move, project_lane

    patch = apply_lane_move(
        {"status": "export_ready", "quality": {"export_ready": True}},
        "rejected",
        reason="证据跑题，需重采",
    )
    assert patch["status"] == "rejected"
    assert patch["quality"]["rejected"] is True
    assert "跑题" in patch["quality"]["reject_reason"]
    assert patch["quality"]["export_ready"] is False

    reopened = apply_lane_move(
        {"status": "rejected", "quality": patch["quality"]},
        "active",
    )
    assert reopened["status"] == "researching"
    assert reopened["quality"]["rejected"] is False
    assert reopened["quality"]["export_ready"] is False
    assert project_lane({**reopened}) == "active"


def test_group_projects_by_lane():
    from cn_social_agent.content.board import group_projects_by_lane

    rows = [
        {"id": "1", "status": "candidate", "short_topic": "A", "topic": "A"},
        {"id": "2", "status": "researching", "short_topic": "B", "topic": "B"},
        {"id": "3", "status": "export_ready", "quality": {"export_ready": True}, "short_topic": "C", "topic": "C"},
        {"id": "4", "status": "rejected", "quality": {"rejected": True, "reject_reason": "x"}, "short_topic": "D", "topic": "D"},
    ]
    lanes = group_projects_by_lane(rows)
    assert [c["id"] for c in lanes["candidate"]] == ["1"]
    assert [c["id"] for c in lanes["active"]] == ["2"]
    assert [c["id"] for c in lanes["export_ready"]] == ["3"]
    assert [c["id"] for c in lanes["rejected"]] == ["4"]
    assert lanes["candidate"][0]["lane"] == "candidate"


def test_normalize_project_exposes_lane():
    from cn_social_agent.content.models import normalize_project

    p = normalize_project({"topic": "x", "status": "candidate"})
    assert p["lane"] == "candidate"
    p2 = normalize_project({"topic": "x", "status": "weird"})
    assert p2["status"] == "researching"
    assert p2["lane"] == "active"


@pytest.mark.asyncio
async def test_board_move_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTENT_PROJECT_DIR", str(tmp_path))
    from cn_social_agent.content import cloud as cloud_mod
    from cn_social_agent.content import service as cps
    from cn_social_agent.content.board import apply_lane_move, project_lane

    cloud_mod.set_content_db(None)
    proj = await cps.create_project(topic="候选选题 Alpha", user_id="u1", email="t@example.com")
    await cps.patch_project(proj["id"], {"status": "candidate"}, user_id="u1", email="t@example.com")
    got = await cps.get_project(proj["id"], user_id="u1", email="t@example.com")
    assert project_lane(got) == "candidate"

    patch = apply_lane_move(got, "active")
    moved = await cps.patch_project(proj["id"], patch, user_id="u1", email="t@example.com")
    assert project_lane(moved) == "active"

    patch2 = apply_lane_move(moved, "rejected", reason="钩子太软")
    rejected = await cps.patch_project(proj["id"], patch2, user_id="u1", email="t@example.com")
    assert project_lane(rejected) == "rejected"
    assert rejected["quality"]["reject_reason"] == "钩子太软"


def _sample_cards():
    return [
        {
            "id": "1",
            "topic": "Agent 工作流",
            "short_topic": "Agent 工作流",
            "category": "AI",
            "evidence_count": 3,
            "canvas_count": 2,
            "journal_id": "j1",
            "video_id": "",
            "presentation_id": "",
            "export_ready": False,
            "updated_at": "2026-08-16T10:00:00Z",
            "created_at": "2026-08-15T10:00:00Z",
            "source_name": "sspai",
        },
        {
            "id": "2",
            "topic": "浏览器扩展合集",
            "short_topic": "浏览器扩展",
            "category": "效率",
            "evidence_count": 8,
            "canvas_count": 0,
            "journal_id": "",
            "video_id": "v1",
            "presentation_id": "p1",
            "export_ready": True,
            "updated_at": "2026-08-16T12:00:00Z",
            "created_at": "2026-08-14T10:00:00Z",
            "source_name": "github",
        },
        {
            "id": "3",
            "topic": "Agent 评测",
            "short_topic": "Agent 评测",
            "category": "AI",
            "evidence_count": 1,
            "canvas_count": 5,
            "journal_id": "",
            "video_id": "",
            "presentation_id": "",
            "export_ready": False,
            "updated_at": "2026-08-16T08:00:00Z",
            "created_at": "2026-08-16T07:00:00Z",
            "source_name": "",
        },
    ]


def test_filter_projects_by_query_category_artifact():
    from cn_social_agent.content.board import filter_projects

    cards = _sample_cards()
    assert [c["id"] for c in filter_projects(cards, query="agent")] == ["1", "3"]
    assert [c["id"] for c in filter_projects(cards, category="AI")] == ["1", "3"]
    assert [c["id"] for c in filter_projects(cards, artifact="canvas")] == ["1", "3"]
    assert [c["id"] for c in filter_projects(cards, artifact="video")] == ["2"]
    assert [c["id"] for c in filter_projects(cards, query="agent", category="AI", artifact="canvas")] == [
        "1",
        "3",
    ]


def test_sort_projects():
    from cn_social_agent.content.board import sort_projects

    cards = _sample_cards()
    by_evidence = sort_projects(cards, "evidence_desc")
    assert [c["id"] for c in by_evidence] == ["2", "1", "3"]
    by_updated = sort_projects(cards, "updated_desc")
    assert [c["id"] for c in by_updated] == ["2", "1", "3"]
    by_created = sort_projects(cards, "created_desc")
    assert [c["id"] for c in by_created] == ["3", "1", "2"]


def test_project_progress_summary():
    from cn_social_agent.content.board import project_progress

    progress = project_progress(
        {
            "evidence_pack": {"evidences": [{"title": "a"}, {"title": "b"}]},
            "canvas": {"nodes": [{"id": "n1"}], "edges": []},
            "artifacts": {"journal_id": "j1", "video_id": "", "presentation_id": "p1"},
            "quality": {"export_ready": True, "gate_pass": True},
        }
    )
    assert progress["evidence"] == 2
    assert progress["canvas"] is True
    assert progress["journal"] is True
    assert progress["presentation"] is True
    assert progress["video"] is False
    assert progress["export_ready"] is True
    assert progress["markers"]["evidence"] is True
    assert progress["markers"]["canvas"] is True
    assert progress["markers"]["journal"] is True
    assert progress["markers"]["presentation"] is True
    assert progress["markers"]["video"] is False


def test_board_card_includes_progress_fields():
    from cn_social_agent.content.board import board_card

    card = board_card(
        {
            "id": "p1",
            "topic": "选题",
            "short_topic": "选题",
            "status": "researching",
            "category": "AI",
            "evidence_pack": {"evidences": [{"title": "e"}]},
            "canvas": {"nodes": [{"id": "n"}]},
            "artifacts": {"journal_id": "j1", "presentation_id": "p1"},
            "quality": {},
        }
    )
    assert card["evidence_count"] == 1
    assert card["canvas_count"] == 1
    assert card["journal_id"] == "j1"
    assert card["presentation_id"] == "p1"
    assert card["progress"]["markers"]["journal"] is True
    assert card["progress"]["markers"]["presentation"] is True
