"""Canvas enhancements — geometry, templates, AI organize helpers/routes."""

from __future__ import annotations

import json
import uuid

import pytest
from aiohttp.test_utils import TestClient, TestServer


def _rect(x: float, y: float, w: float = 240, h: float = 150, **extra):
    return {"x": x, "y": y, "w": w, "h": h, **extra}


def _point_on_rect_boundary(px: float, py: float, node: dict, *, tol: float = 0.6) -> bool:
    x, y, w, h = float(node["x"]), float(node["y"]), float(node["w"]), float(node["h"])
    on_left = abs(px - x) <= tol and y - tol <= py <= y + h + tol
    on_right = abs(px - (x + w)) <= tol and y - tol <= py <= y + h + tol
    on_top = abs(py - y) <= tol and x - tol <= px <= x + w + tol
    on_bottom = abs(py - (y + h)) <= tol and x - tol <= px <= x + w + tol
    return on_left or on_right or on_top or on_bottom


def _rects_overlap(a: dict, b: dict) -> bool:
    return not (
        a["x"] + a["w"] <= b["x"]
        or b["x"] + b["w"] <= a["x"]
        or a["y"] + a["h"] <= b["y"]
        or b["y"] + b["h"] <= a["y"]
    )


# ----- Task 1: geometry + templates -----


def test_edge_endpoints_lie_on_boundaries_not_centers():
    from cn_social_agent.content.canvas_geometry import edge_endpoints

    a = _rect(40, 40)
    b = _rect(400, 200)
    x1, y1, x2, y2 = edge_endpoints(a, b)
    cx1, cy1 = a["x"] + a["w"] / 2, a["y"] + a["h"] / 2
    cx2, cy2 = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
    assert (x1, y1) != pytest.approx((cx1, cy1), abs=1)
    assert (x2, y2) != pytest.approx((cx2, cy2), abs=1)
    assert _point_on_rect_boundary(x1, y1, a)
    assert _point_on_rect_boundary(x2, y2, b)


def test_edge_endpoints_horizontal_vertical_and_overlap():
    from cn_social_agent.content.canvas_geometry import edge_endpoints

    left = _rect(40, 100)
    right = _rect(400, 100)
    x1, y1, x2, y2 = edge_endpoints(left, right)
    assert abs(y1 - (left["y"] + left["h"] / 2)) < 1
    assert abs(y2 - (right["y"] + right["h"] / 2)) < 1
    assert _point_on_rect_boundary(x1, y1, left)
    assert _point_on_rect_boundary(x2, y2, right)

    top = _rect(100, 40)
    bottom = _rect(100, 400)
    x1, y1, x2, y2 = edge_endpoints(top, bottom)
    assert abs(x1 - (top["x"] + top["w"] / 2)) < 1
    assert abs(x2 - (bottom["x"] + bottom["w"] / 2)) < 1
    assert _point_on_rect_boundary(x1, y1, top)
    assert _point_on_rect_boundary(x2, y2, bottom)

    same = _rect(80, 80)
    twin = _rect(80, 80)
    pts = edge_endpoints(same, twin)
    assert len(pts) == 4
    assert all(isinstance(v, (int, float)) for v in pts)


def test_curve_path_returns_cubic_svg():
    from cn_social_agent.content.canvas_geometry import curve_path

    a = _rect(40, 40)
    b = _rect(360, 280)
    d = curve_path(a, b)
    assert d.startswith("M ")
    assert " C " in d
    tokens = d.replace(",", " ").split()
    assert tokens[0] == "M"
    assert "C" in tokens
    # M x y C c1x c1y c2x c2y x y → 8 numbers after commands
    nums = [float(t) for t in tokens if t not in ("M", "C")]
    assert len(nums) == 8


def test_list_and_instantiate_canvas_templates():
    from cn_social_agent.content.canvas import normalize_canvas
    from cn_social_agent.content.canvas_templates import (
        instantiate_canvas_template,
        list_canvas_templates,
    )

    catalog = list_canvas_templates()
    ids = {t["id"] for t in catalog}
    assert ids == {"blank", "topic_funnel", "script_structure", "swot"}
    assert all(t.get("label") for t in catalog)

    blank = instantiate_canvas_template("blank")
    assert blank["nodes"] == []
    assert blank["edges"] == []

    funnel = instantiate_canvas_template("topic_funnel")
    again = instantiate_canvas_template("topic_funnel")
    # structure/layout deterministic, ids unique per instantiation
    assert [n["title"] for n in funnel["nodes"]] == [n["title"] for n in again["nodes"]]
    assert [(n["x"], n["y"]) for n in funnel["nodes"]] == [
        (n["x"], n["y"]) for n in again["nodes"]
    ]
    assert [e["label"] for e in funnel["edges"]] == [e["label"] for e in again["edges"]]
    assert not ({n["id"] for n in funnel["nodes"]} & {n["id"] for n in again["nodes"]})
    assert not ({e["id"] for e in funnel["edges"]} & {e["id"] for e in again["edges"]})
    assert len(funnel["nodes"]) >= 3
    assert all(n.get("title") for n in funnel["nodes"])
    # Chinese labels present
    titles = " ".join(n["title"] for n in funnel["nodes"])
    assert any("\u4e00" <= ch <= "\u9fff" for ch in titles)

    norm = normalize_canvas(funnel)
    assert norm["count"] == len(funnel["nodes"])
    assert len(norm["edges"]) == len(funnel["edges"])
    known = {n["id"] for n in norm["nodes"]}
    for edge in norm["edges"]:
        assert edge["from"] in known and edge["to"] in known

    for i, a in enumerate(norm["nodes"]):
        for b in norm["nodes"][i + 1 :]:
            assert not _rects_overlap(a, b), f"{a['id']} overlaps {b['id']}"

    for tid in ("script_structure", "swot"):
        board = normalize_canvas(instantiate_canvas_template(tid))
        assert board["count"] >= 4
        for i, a in enumerate(board["nodes"]):
            for b in board["nodes"][i + 1 :]:
                assert not _rects_overlap(a, b)

    with pytest.raises(ValueError):
        instantiate_canvas_template("nope")


# ----- Task 2: AI helpers + routes -----


def test_canvas_ai_select_payload_and_validate():
    from cn_social_agent.content.canvas import normalize_canvas
    from cn_social_agent.content.canvas_ai import (
        build_organize_payload,
        merge_organize_result,
        select_nodes_for_organize,
        validate_organize_output,
    )

    canvas = normalize_canvas(
        {
            "nodes": [
                {"id": "nd_a", "kind": "note", "title": "灵感", "text": "扩展合集"},
                {"id": "nd_b", "kind": "hook", "title": "钩子", "text": "一句话"},
                {"id": "nd_c", "kind": "outline", "title": "结构", "text": "三段"},
            ],
            "edges": [{"from": "nd_a", "to": "nd_b"}],
        }
    )
    selected = select_nodes_for_organize(canvas, ["nd_a", "nd_b", "missing"])
    assert [n["id"] for n in selected] == ["nd_a", "nd_b"]

    payload = build_organize_payload(
        canvas, [n["id"] for n in selected], instruction="归类并补钩子"
    )
    assert payload["instruction"] == "归类并补钩子"
    assert {n["id"] for n in payload["nodes"]} == {"nd_a", "nd_b"}
    # edges derive from the canvas itself — callers cannot forget to pass them
    assert [(e["from"], e["to"]) for e in payload["edges"]] == [("nd_a", "nd_b")]
    # editable fields the model may return must be visible in the payload
    assert set(payload["nodes"][0]) >= {"id", "kind", "title", "text", "tags", "color", "url", "done"}

    good = {
        "nodes": [
            {"id": "nd_a", "kind": "note", "title": "选题灵感", "text": "扩展合集"},
            {"id": "nd_b", "kind": "hook", "title": "开场钩子", "text": "你还在乱开标签页？"},
        ],
        "edges": [{"from": "nd_a", "to": "nd_b", "label": "引出"}],
    }
    validated = validate_organize_output(good, allowed_ids={"nd_a", "nd_b"})
    assert validated["nodes"][0]["id"] == "nd_a"
    assert validated["edges"][0]["label"] == "引出"

    with pytest.raises(ValueError):
        validate_organize_output(
            {"nodes": [{"id": "nd_x", "kind": "note", "title": "x"}], "edges": []},
            allowed_ids={"nd_a", "nd_b"},
        )
    with pytest.raises(ValueError):
        validate_organize_output(
            {"nodes": [{"id": "nd_a", "kind": "weird", "title": "x"}], "edges": []},
            allowed_ids={"nd_a"},
        )
    with pytest.raises(ValueError):
        validate_organize_output(
            {
                "nodes": [{"id": "nd_a", "kind": "note", "title": "x"}],
                "edges": [{"from": "nd_a", "to": "nd_z"}],
            },
            allowed_ids={"nd_a"},
        )

    merged = merge_organize_result(canvas, validated)
    by_id = {n["id"]: n for n in merged["nodes"]}
    assert by_id["nd_a"]["title"] == "选题灵感"
    assert by_id["nd_c"]["title"] == "结构"  # untouched
    assert any(e["from"] == "nd_a" and e["to"] == "nd_b" for e in merged["edges"])


def test_merge_keeps_cross_selection_edges_and_omitted_fields():
    from cn_social_agent.content.canvas import normalize_canvas
    from cn_social_agent.content.canvas_ai import merge_organize_result, validate_organize_output

    canvas = normalize_canvas(
        {
            "nodes": [
                {
                    "id": "nd_a",
                    "kind": "note",
                    "title": "灵感",
                    "text": "扩展合集",
                    "color": "green",
                    "url": "https://a.test",
                    "done": True,
                    "tags": ["sspai"],
                },
                {"id": "nd_b", "kind": "hook", "title": "钩子", "text": "一句话"},
                {"id": "nd_c", "kind": "outline", "title": "结构", "text": "三段"},
            ],
            "edges": [
                {"from": "nd_a", "to": "nd_b", "label": "选中内部"},
                {"from": "nd_a", "to": "nd_c", "label": "跨选区"},
                {"from": "nd_c", "to": "nd_b", "label": "跨选区反向"},
            ],
        }
    )
    validated = validate_organize_output(
        {
            "nodes": [
                {"id": "nd_a", "title": "选题灵感"},
                {"id": "nd_b", "kind": "hook", "title": "开场钩子"},
            ],
            "edges": [{"from": "nd_b", "to": "nd_a", "label": "回指"}],
        },
        allowed_ids={"nd_a", "nd_b"},
    )
    # only explicitly returned keys are carried
    assert "color" not in validated["nodes"][0]
    assert "kind" not in validated["nodes"][0]

    merged = merge_organize_result(canvas, validated)
    by_id = {n["id"]: n for n in merged["nodes"]}
    assert by_id["nd_a"]["title"] == "选题灵感"
    assert by_id["nd_a"]["color"] == "green"
    assert by_id["nd_a"]["url"] == "https://a.test"
    assert by_id["nd_a"]["done"] is True
    assert by_id["nd_a"]["tags"] == ["sspai"]

    pairs = {(e["from"], e["to"]) for e in merged["edges"]}
    # cross-selection edges survive
    assert ("nd_a", "nd_c") in pairs
    assert ("nd_c", "nd_b") in pairs
    # intra-selection edges are replaced by the AI result
    assert ("nd_b", "nd_a") in pairs
    assert ("nd_a", "nd_b") not in pairs


def test_validate_rejects_dangerous_url_scheme():
    from cn_social_agent.content.canvas_ai import validate_organize_output

    ok = validate_organize_output(
        {"nodes": [{"id": "nd_a", "url": "https://ok.test"}], "edges": []},
        allowed_ids={"nd_a"},
    )
    assert ok["nodes"][0]["url"] == "https://ok.test"

    empty = validate_organize_output(
        {"nodes": [{"id": "nd_a", "url": ""}], "edges": []},
        allowed_ids={"nd_a"},
    )
    assert empty["nodes"][0]["url"] == ""

    for bad in ("javascript:alert(1)", "data:text/html,<script>", "file:///etc/passwd"):
        with pytest.raises(ValueError):
            validate_organize_output(
                {"nodes": [{"id": "nd_a", "url": bad}], "edges": []},
                allowed_ids={"nd_a"},
            )


def test_validate_organize_output_accepts_json_string():
    from cn_social_agent.content.canvas_ai import validate_organize_output

    raw = json.dumps(
        {
            "nodes": [{"id": "nd_1", "kind": "note", "title": "A", "text": "t"}],
            "edges": [],
        },
        ensure_ascii=False,
    )
    out = validate_organize_output(raw, allowed_ids={"nd_1"})
    assert out["nodes"][0]["title"] == "A"


@pytest.mark.asyncio
async def test_canvas_template_and_organize_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKBENCH_STORE", "memory")
    monkeypatch.setenv("WORKBENCH_LLM", "mock")
    monkeypatch.setenv("CANVAS_BOARD_DIR", str(tmp_path / "boards"))
    from cn_social_agent.api import create_app

    app = create_app()
    async with TestClient(TestServer(app)) as client:
        email = f"cv-{uuid.uuid4().hex[:10]}@example.com"
        reg = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "secret123"},
        )
        assert reg.status == 200
        token = (await reg.json())["accessToken"]
        headers = {"Authorization": f"Bearer {token}"}

        tpl = await client.get("/api/canvas/templates", headers=headers)
        assert tpl.status == 200
        body = await tpl.json()
        ids = {t["id"] for t in body["templates"]}
        assert "topic_funnel" in ids and "swot" in ids

        created = await client.post(
            "/api/canvas/boards",
            headers=headers,
            json={"title": "漏斗画布", "template_id": "topic_funnel"},
        )
        assert created.status == 200
        data = await created.json()
        canvas = data["canvas"]
        assert canvas["title"] == "漏斗画布"
        assert canvas["count"] >= 3
        assert len(canvas["edges"]) >= 1

        blank = await client.post(
            "/api/canvas/boards",
            headers=headers,
            json={"title": "空画布", "template_id": "blank"},
        )
        assert blank.status == 200
        assert (await blank.json())["canvas"]["count"] == 0

        node_ids = [n["id"] for n in canvas["nodes"][:2]]
        org = await client.post(
            "/api/canvas/organize",
            headers=headers,
            json={
                "board_id": canvas["board_id"],
                "node_ids": node_ids,
                "instruction": "整理",
            },
        )
        # Mock LLM is not a production organizer — must not mutate
        assert org.status == 503
        err = await org.json()
        assert "AI 整理暂不可用" in (err.get("error") or "")

        # Invalid template
        bad = await client.post(
            "/api/canvas/boards",
            headers=headers,
            json={"title": "坏", "template_id": "nope"},
        )
        assert bad.status == 400


async def _auth_headers(client) -> dict[str, str]:
    email = f"cv-{uuid.uuid4().hex[:10]}@example.com"
    reg = await client.post("/api/auth/register", json={"email": email, "password": "secret123"})
    assert reg.status == 200
    return {"Authorization": f"Bearer {(await reg.json())['accessToken']}"}


class _FakeLLM:
    """Stand-in for a configured workbench LLM (not MockLLM)."""

    def __init__(self, content: Any = "", error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.calls = 0

    async def chat_completion(self, messages, model: str = "", **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        text = self.content if isinstance(self.content, str) else json.dumps(self.content)
        return {"choices": [{"message": {"role": "assistant", "content": text}}]}


@pytest.mark.asyncio
async def test_unknown_board_id_is_404_on_mutating_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKBENCH_STORE", "memory")
    monkeypatch.setenv("WORKBENCH_LLM", "mock")
    monkeypatch.setenv("CANVAS_BOARD_DIR", str(tmp_path / "boards"))
    from cn_social_agent.api import create_app

    app = create_app()
    async with TestClient(TestServer(app)) as client:
        headers = await _auth_headers(client)
        base = await client.get("/api/canvas", headers=headers)
        assert base.status == 200
        before = await base.json()
        real_board_id = before["canvas"]["board_id"]
        board_count_before = len(before["boards"])

        ghost = "cv_doesnotexist"
        cases = [
            ("put", "/api/canvas", {"board_id": ghost, "nodes": [{"kind": "note", "text": "x"}]}),
            ("post", "/api/canvas/arrange", {"board_id": ghost}),
            ("post", "/api/canvas/handoff", {"board_id": ghost, "node_ids": []}),
            (
                "post",
                "/api/canvas/organize",
                {"board_id": ghost, "node_ids": ["nd_x"], "instruction": "整理"},
            ),
        ]
        for method, path, payload in cases:
            resp = await getattr(client, method)(path, headers=headers, json=payload)
            assert resp.status == 404, f"{path} → {resp.status}"

        after = await client.get("/api/canvas", headers=headers)
        data = await after.json()
        assert len(data["boards"]) == board_count_before
        assert {b["board_id"] for b in data["boards"]} == {
            b["board_id"] for b in before["boards"]
        }
        assert data["canvas"]["board_id"] == real_board_id
        assert data["canvas"]["count"] == before["canvas"]["count"]


@pytest.mark.asyncio
async def test_organize_success_persists_and_bad_output_is_422(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKBENCH_STORE", "memory")
    monkeypatch.setenv("WORKBENCH_LLM", "mock")
    monkeypatch.setenv("CANVAS_BOARD_DIR", str(tmp_path / "boards"))
    from cn_social_agent.api import create_app

    app = create_app()
    async with TestClient(TestServer(app)) as client:
        headers = await _auth_headers(client)
        created = await client.post(
            "/api/canvas/boards",
            headers=headers,
            json={
                "title": "整理板",
                "nodes": [
                    {
                        "id": "nd_a",
                        "kind": "note",
                        "title": "灵感",
                        "text": "扩展合集",
                        "color": "green",
                        "url": "https://a.test",
                    },
                    {"id": "nd_b", "kind": "hook", "title": "钩子", "text": "一句话"},
                ],
                "edges": [{"from": "nd_a", "to": "nd_b"}],
            },
        )
        assert created.status == 200
        canvas = (await created.json())["canvas"]
        board_id = canvas["board_id"]
        ids = [n["id"] for n in canvas["nodes"]]

        state = app["state"]
        good = {
            "nodes": [
                {"id": ids[0], "kind": "note", "title": "选题灵感"},
                {"id": ids[1], "kind": "hook", "title": "开场钩子"},
            ],
            "edges": [{"from": ids[1], "to": ids[0], "label": "回指"}],
        }
        state.agent.llm = _FakeLLM(content=good)
        ok = await client.post(
            "/api/canvas/organize",
            headers=headers,
            json={"board_id": board_id, "node_ids": ids, "instruction": "整理"},
        )
        assert ok.status == 200
        saved = (await ok.json())["canvas"]
        by_id = {n["id"]: n for n in saved["nodes"]}
        assert by_id[ids[0]]["title"] == "选题灵感"
        assert by_id[ids[0]]["color"] == "green"
        assert by_id[ids[0]]["url"] == "https://a.test"
        assert any(e["from"] == ids[1] and e["to"] == ids[0] for e in saved["edges"])

        reloaded = await client.get(
            f"/api/canvas?board_id={board_id}", headers=headers
        )
        persisted = (await reloaded.json())["canvas"]
        assert {n["id"]: n["title"] for n in persisted["nodes"]}[ids[0]] == "选题灵感"

        # Invalid model output → validation error, board unchanged
        state.agent.llm = _FakeLLM(content="not json at all")
        bad = await client.post(
            "/api/canvas/organize",
            headers=headers,
            json={"board_id": board_id, "node_ids": ids, "instruction": "整理"},
        )
        assert bad.status == 422
        assert "AI 整理" in ((await bad.json()).get("error") or "")

        # Transport failure → unavailable
        state.agent.llm = _FakeLLM(error=RuntimeError("connection reset"))
        down = await client.post(
            "/api/canvas/organize",
            headers=headers,
            json={"board_id": board_id, "node_ids": ids, "instruction": "整理"},
        )
        assert down.status == 503
        assert "AI 整理暂不可用" in ((await down.json()).get("error") or "")

        final = await client.get(f"/api/canvas?board_id={board_id}", headers=headers)
        unchanged = (await final.json())["canvas"]
        assert {n["id"]: n["title"] for n in unchanged["nodes"]}[ids[0]] == "选题灵感"
