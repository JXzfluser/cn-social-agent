"""Knowledge canvas — nodes, seeding, handoff."""

from __future__ import annotations

import pytest


def test_normalize_node_defaults_and_snap():
    from cn_social_agent.content.canvas import normalize_node

    node = normalize_node({"kind": "weird", "text": "x" * 5000, "x": 13.4, "y": -20})
    assert node["kind"] == "note"
    assert len(node["text"]) == 4000
    assert node["x"] % 8 == 0
    assert node["y"] == 0
    assert node["id"].startswith("nd_")


def test_normalize_canvas_caps_nodes():
    from cn_social_agent.content.canvas import MAX_NODES, normalize_canvas

    canvas = normalize_canvas({"nodes": [{"kind": "note"} for _ in range(MAX_NODES + 30)]})
    assert canvas["count"] == MAX_NODES
    assert canvas["nodes"][0]["kind"] == "note"


def test_seed_nodes_from_project():
    from cn_social_agent.content.canvas import seed_nodes_from_project

    nodes = seed_nodes_from_project(
        {
            "topic": "浏览器扩展合集：效率向",
            "short_topic": "浏览器扩展合集",
            "research_notes": "原文提到 5 个扩展",
            "why": "热度高",
            "search_terms": ["浏览器扩展", "效率工具"],
            "evidence_pack": {
                "evidences": [
                    {"title": "扩展 A", "summary": "说明", "url": "https://a.test", "source": "sspai"}
                ]
            },
        }
    )
    kinds = [n["kind"] for n in nodes]
    assert "outline" in kinds
    assert "note" in kinds
    assert "hook" in kinds
    assert "evidence" in kinds
    assert "question" in kinds
    ev = next(n for n in nodes if n["kind"] == "evidence")
    assert ev["url"] == "https://a.test"


def test_merge_seed_skips_duplicates():
    from cn_social_agent.content.canvas import merge_seed_nodes, normalize_canvas

    existing = normalize_canvas(
        {"nodes": [{"kind": "evidence", "title": "扩展 A", "url": "https://a.test"}]}
    )
    seed = [
        {"kind": "evidence", "title": "扩展 A", "url": "https://a.test"},
        {"kind": "evidence", "title": "扩展 B", "url": "https://b.test"},
    ]
    merged = merge_seed_nodes(existing, seed)
    assert merged["added"] == 1
    assert merged["count"] == 2


def test_canvas_to_handoff_selected_nodes():
    from cn_social_agent.content.canvas import canvas_to_handoff, normalize_canvas

    canvas = normalize_canvas(
        {
            "nodes": [
                {"id": "nd_1", "kind": "outline", "title": "选题", "text": "浏览器扩展合集"},
                {
                    "id": "nd_2",
                    "kind": "evidence",
                    "title": "扩展 A",
                    "text": "支持分组",
                    "url": "https://a.test",
                    "tags": ["sspai"],
                },
                {"id": "nd_3", "kind": "note", "title": "先不用", "text": "跑题"},
            ]
        }
    )
    out = canvas_to_handoff(canvas, ["nd_1", "nd_2"])
    assert out["node_count"] == 2
    assert "浏览器扩展合集" in out["topic"]
    assert "https://a.test" in out["urls"]
    assert "跑题" not in out["research_notes"]
    assert "sspai" in out["search_terms"]


def test_canvas_to_handoff_all_when_no_selection():
    from cn_social_agent.content.canvas import canvas_to_handoff, normalize_canvas

    canvas = normalize_canvas({"nodes": [{"kind": "note", "text": "a"}, {"kind": "note", "text": "b"}]})
    out = canvas_to_handoff(canvas, [])
    assert out["node_count"] == 2


def test_project_model_keeps_canvas():
    from cn_social_agent.content.models import normalize_project

    proj = normalize_project(
        {"topic": "t", "canvas": {"nodes": [{"kind": "note", "text": "hi"}]}}
    )
    assert proj["canvas"]["nodes"][0]["text"] == "hi"


def test_prefs_keep_canvas_scratch():
    from cn_social_agent.api.prefs import merge_prefs, normalize_prefs

    merged = merge_prefs({}, {"canvas_scratch": {"nodes": [{"kind": "hook", "text": "钩子"}]}})
    assert merged["canvas_scratch"]["nodes"][0]["text"] == "钩子"
    assert normalize_prefs(merged)["canvas_scratch"]["nodes"]


@pytest.mark.asyncio
async def test_canvas_persists_on_project(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTENT_PROJECT_DIR", str(tmp_path))
    from cn_social_agent.content import cloud as cloud_mod
    from cn_social_agent.content import service as cps
    from cn_social_agent.content.canvas import (
        merge_seed_nodes,
        normalize_canvas,
        seed_nodes_from_project,
    )

    cloud_mod.set_content_db(None)
    proj = await cps.create_project(
        topic="浏览器扩展合集：6 款新玩意",
        user_id="u1",
        email="t@example.com",
        research_notes="Tab Manager Plus 能管理大量标签页。",
    )
    seeded = merge_seed_nodes(
        normalize_canvas(proj.get("canvas"), project_id=proj["id"]),
        seed_nodes_from_project(proj),
    )
    assert seeded["count"] >= 2

    patched = await cps.patch_project(
        proj["id"],
        {"canvas": {"nodes": seeded["nodes"], "updated_at": seeded["updated_at"]}},
        user_id="u1",
        email="t@example.com",
    )
    assert len(patched["canvas"]["nodes"]) == seeded["count"]

    reloaded = await cps.get_project(proj["id"], user_id="u1", email="t@example.com")
    kinds = {n["kind"] for n in reloaded["canvas"]["nodes"]}
    assert "outline" in kinds and "note" in kinds


def test_edges_color_done_and_markdown():
    from cn_social_agent.content.canvas import (
        auto_arrange,
        canvas_to_markdown,
        normalize_canvas,
    )

    canvas = normalize_canvas(
        {
            "title": "Agent 流水线",
            "nodes": [
                {"id": "a", "kind": "outline", "title": "计划", "text": "GPT", "color": "yellow"},
                {"id": "b", "kind": "note", "title": "执行", "text": "DeepSeek", "done": True},
                {"id": "c", "kind": "hook", "title": "验收", "text": "Claude"},
            ],
            "edges": [
                {"from": "a", "to": "b", "label": "handoff"},
                {"from": "b", "to": "c"},
                {"from": "a", "to": "missing"},
            ],
        }
    )
    assert len(canvas["edges"]) == 2
    assert canvas["nodes"][0]["color"] == "yellow"
    assert canvas["nodes"][1]["done"] is True
    md = canvas_to_markdown(canvas)
    assert "# Agent 流水线" in md
    assert "计划" in md
    assert "handoff" in md
    arranged = auto_arrange(canvas)
    xs = {n["kind"]: n["x"] for n in arranged["nodes"]}
    assert xs["outline"] != xs["note"]


@pytest.mark.asyncio
async def test_standalone_board_persists_across_reload(tmp_path, monkeypatch):
    monkeypatch.setenv("CANVAS_BOARD_DIR", str(tmp_path))
    from cn_social_agent.content import canvas_store as cvs

    board = cvs.ensure_default_board(
        user_id="u1",
        email="t@example.com",
        legacy={"nodes": [{"kind": "note", "title": "旧速记", "text": "hello"}]},
    )
    assert board["count"] == 1
    assert board["title"] == "速记画布"

    saved = cvs.save_board(
        {
            "id": board["board_id"],
            "title": "我的白板",
            "nodes": [
                {"id": "nd_a", "kind": "note", "title": "旧速记", "text": "hello"},
                {"id": "nd_b", "kind": "hook", "title": "钩子", "text": "别丢"},
            ],
            "edges": [{"from": "nd_a", "to": "nd_b", "label": "下一步"}],
        },
        user_id="u1",
        email="t@example.com",
    )
    assert saved["title"] == "我的白板"
    assert saved["count"] == 2
    assert len(saved["edges"]) == 1

    again = cvs.get_board(board["board_id"], user_id="u1", email="t@example.com")
    assert again is not None
    assert again["nodes"][1]["text"] == "别丢"
    assert again["edges"][0]["label"] == "下一步"

    first = cvs.ensure_default_board(user_id="u1", email="t@example.com")
    assert first["board_id"] == board["board_id"]


def test_prefs_extras_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("USER_PREFS_DIR", str(tmp_path))
    from cn_social_agent.api.prefs_local import merge_extras, write_extras

    write_extras(
        "user_x",
        {
            "connectors_enabled": {"weixin": True},
            "canvas_scratch": {"nodes": [{"kind": "note"}]},
            "default_audience": "should-not-be-written",
        },
    )
    merged = merge_extras("user_x", {"default_audience": "创业者", "llm_mode": "cloud"})
    assert merged["default_audience"] == "创业者"
    assert merged["connectors_enabled"]["weixin"] is True
    assert "canvas_scratch" in merged
