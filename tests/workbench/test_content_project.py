"""Content Project S1 unit tests."""

from __future__ import annotations

import pytest


def test_normalize_distills_short_topic():
    from cn_social_agent.content.models import normalize_project

    p = normalize_project(
        {
            "topic": "浏览器扩展合集：我们为你找到了这 6 款实用、有趣的「新玩意」",
            "user_id": "u1",
        }
    )
    assert p["short_topic"] == "浏览器扩展合集"
    assert p["id"].startswith("cp_")
    assert p["status"] == "researching"
    assert p["evidence_pack"]["count"] == 0


def test_local_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTENT_PROJECT_DIR", str(tmp_path))
    from cn_social_agent.content.models import normalize_project
    from cn_social_agent.content.store_local import get_project, list_projects, save_project

    p = normalize_project({"topic": "Grok Build", "user_id": "u1", "email": "a@b.c"})
    saved = save_project(p, user_id="u1", email="a@b.c")
    got = get_project(saved["id"], user_id="u1", email="a@b.c")
    assert got is not None
    assert got["short_topic"] == "Grok Build"
    assert any(x["id"] == saved["id"] for x in list_projects(user_id="u1", email="a@b.c"))


@pytest.mark.asyncio
async def test_upsert_and_patch_local(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTENT_PROJECT_DIR", str(tmp_path))
    from cn_social_agent.content import cloud as cloud_mod
    from cn_social_agent.content import service as cps

    cloud_mod.set_content_db(None)
    created = await cps.create_project(
        topic="浏览器扩展合集：我们为你找到了这 6 款",
        user_id="u1",
        email="t@example.com",
        research_notes="Multi-highlight 是一款网页高亮浏览器扩展。",
        category="product_explain",
    )
    assert created["id"].startswith("cp_")
    assert created["short_topic"] == "浏览器扩展合集"
    assert created["persisted"] == "local"

    patched = await cps.patch_project(
        created["id"],
        {"evidence_pack": {"evidences": [{"id": "e1", "text": "x" * 50}], "count": 1}},
        user_id="u1",
        email="t@example.com",
    )
    assert patched["evidence_pack"]["count"] == 1

    attached = await cps.attach_artifacts(
        created["id"],
        user_id="u1",
        email="t@example.com",
        journal_id="h_abc",
    )
    assert attached["artifacts"]["journal_id"] == "h_abc"


@pytest.mark.asyncio
async def test_handoff_creates_content_project(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTENT_PROJECT_DIR", str(tmp_path))
    from cn_social_agent.content import cloud as cloud_mod
    from cn_social_agent.tools.hotspot_handoff import build_handoff_payload
    from cn_social_agent.content import service as cps

    cloud_mod.set_content_db(None)
    out = await build_handoff_payload(
        title="浏览器扩展合集：我们为你找到了这 6 款实用、有趣的「新玩意」",
        url="https://example.com/x",
        source="sspai",
        why="好玩",
        track="journal",
        research_notes="Tab Manager Plus 能管理大量标签页。",
    )
    assert out["ok"]
    assert out["short_topic"] == "浏览器扩展合集"
    proj = await cps.create_project(
        topic=out["short_topic"],
        user_id="u1",
        email="t@example.com",
        category=out.get("category") or "",
        research_notes=out.get("research_notes") or "",
        search_terms=out.get("search_terms"),
        source={"kind": "hotspot", "url": out.get("url") or "", "name": "sspai"},
    )
    assert proj["research_notes"]
    assert "Tab Manager" in proj["research_notes"] or "标签" in proj["research_notes"]
