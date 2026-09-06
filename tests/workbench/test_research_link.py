"""Compound-loop tests: Content Project ↔ video pipeline research linking."""

from __future__ import annotations

import pytest


@pytest.fixture()
def local_projects(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTENT_PROJECT_DIR", str(tmp_path))
    from cn_social_agent.content import cloud as cloud_mod

    cloud_mod.set_content_db(None)
    return cloud_mod


def test_project_research_notes_formats_notes_and_evidence(local_projects):
    from cn_social_agent.content.research_link import project_research_notes

    proj = {
        "research_notes": "Hotspot handoff：LangGraph 1.0 发布，图编排成为默认。",
        "evidence_pack": {
            "count": 2,
            "evidences": [
                {"id": "e1", "text": "LangGraph 1.0 引入 checkpoint 持久化", "score": 0.9, "url": "h"},
                {"id": "e2", "text": "官方 migration guide 覆盖 0.x 升级", "score": 0.5, "url": "g"},
            ],
        },
    }
    notes = project_research_notes(proj)
    assert "项目调研笔记" in notes
    assert "LangGraph 1.0 发布" in notes
    assert "本地证据包" in notes or "项目证据包" in notes
    assert "[e1]" in notes


def test_project_research_notes_empty():
    from cn_social_agent.content.research_link import project_research_notes

    assert project_research_notes({}) == ""
    assert project_research_notes(None) == ""


@pytest.mark.asyncio
async def test_attach_video_artifact_without_project(local_projects):
    from cn_social_agent.content.research_link import attach_video_artifact

    out = await attach_video_artifact(
        user_id="u1",
        email="t@example.com",
        topic="从无项目主题",
        video_id="vp_x",
    )
    assert out is None
