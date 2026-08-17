"""Knowledge cards build / history / tools tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cn_social_agent.agent.mode import PRODUCE_TOOLS, detect_mode
from cn_social_agent.cards.build import build_cards, fallback_payload, normalize_llm_payload
from cn_social_agent.cards.history import (
    delete_history_item,
    get_history_item,
    list_history_summaries,
    save_history_record,
)
from cn_social_agent.cards.service import parse_roles
from cn_social_agent.tools.builtin import (
    register_builtin_tools,
    tool_present_knowledge_card,
    tool_propose_knowledge_cards,
    tool_scan_knowledge_cards,
)
from cn_social_agent.tools.registry import ToolRegistry


def test_categories_list():
    from cn_social_agent.cards.categories import get_category, list_categories

    cats = list_categories()
    assert len(cats) >= 4
    assert get_category("product_explain")["label"] == "产品科普"
    assert get_category("nope")["id"] == "hiring_insight"
    by_id = {c["id"]: c for c in cats}
    assert by_id["hiring_insight"]["cover_layout"] == "classic"
    assert by_id["product_explain"]["cover_layout"] == "split"
    assert by_id["skill_roadmap"]["know_layout"] == "roadmap"
    assert by_id["industry_brief"]["know_layout"] == "brief"
    assert by_id["hiring_insight"]["preview"]["cover"]["title"]


def test_parse_roles():
    assert parse_roles("A、B,C") == ["A", "B", "C"]
    assert len(parse_roles("")) == 3


def test_snippet_quality_filters_dictionary_noise():
    from cn_social_agent.cards.scrape import filter_snippets, is_useful_snippet, pick_market_note

    junk = (
        "独立（拼音：dú lì，注音：ㄉㄨˊ ㄌㄧˋ），汉语词语，指不依附他者的存在状态。"
        "其含义包括单独站立、自主生活。"
    )
    nav = (
        "1 天前 AI工具集官网收录了国内外数百个AI工具，该导航网站包括AI写作工具、"
        "AI图像生成和背景移除、AI视频剪辑等分类。"
    )
    jd = (
        "招聘 AI Agent 开发工程师：岗位职责含 LangGraph 编排、工具调用与状态机设计，"
        "任职要求三年经验，能交付可观测的多智能体工作流。"
    )
    assert not is_useful_snippet(junk, role="独立开发者")
    assert not is_useful_snippet(nav)
    assert is_useful_snippet(jd, role="AI Agent 开发工程师")
    assert filter_snippets([junk, nav, jd], role="独立开发者") == [jd]
    assert "LangGraph" in pick_market_note([junk, jd])
    assert pick_market_note([junk, nav]) == ""


def test_build_cards_cached_when_few_snippets():
    out = build_cards(
        ["AI Agent 开发工程师"],
        [["langgraph agent 工具调用 智能体编排 经验要求三年"]],
    )
    assert out["cover"]["title"]
    assert len(out["knowledge"]) == 3
    assert out["mode"] in ("live", "cached")


def test_fallback_payload():
    out = fallback_payload(["X"])
    assert out["mode"] == "cached"
    assert len(out["knowledge"]) == 3


def test_clip_and_normalize_limits():
    from cn_social_agent.cards.build import clip, normalize_llm_payload

    assert clip("短", 10) == "短"
    assert "…" in clip("这是一段很长很长的测试文字用于裁剪", 8)
    out = normalize_llm_payload(
        {
            "cover": {
                "title": "超长标题" * 10,
                "description": "导语" * 40,
                "tags": ["很长的标签名啊啊啊", "b", "c", "d", "e"],
            },
            "knowledge": [
                {
                    "topicTitle": "超长主题名称需要被裁剪掉多余部分",
                    "concept": "概念" * 50,
                    "keyPoint": "- 第一条要点很长很长很长很长很长很长\n- 二\n- 三\n- 四",
                    "example": "例子" * 40,
                }
            ],
        },
        ["岗"],
    )
    assert len(out["cover"]["title"]) <= 48
    assert len(out["knowledge"][0]["topicTitle"]) <= 40
    assert len(out["knowledge"][0]["realPoints"]) <= 5
    assert out["knowledge"][0].get("card_kind")
    assert out["cover"].get("visual_style")
    assert out.get("visual_style")


def test_titles_and_flow_keep_complete_terms():
    from cn_social_agent.cards.build import (
        clip_complete,
        normalize_llm_payload,
        short_step,
    )

    assert short_step("定义StateGraph状态Schema，明确节点间传递的数据结构") == "定义StateGraph"
    assert short_step("接入Checkpointer，支持状态持久化") == "接入Checkpointer"
    assert "LangGraph" in clip_complete("独立开发者与全栈工程师的LangGraph能力图鉴", 18)
    out = normalize_llm_payload(
        {
            "cover": {
                "title": "独立开发者与全栈工程师的LangGraph能力图鉴",
                "description": "导语" * 20,
            },
            "knowledge": [
                {
                    "topicTitle": "LangGraph与LangChain分工",
                    "card_kind": "steps",
                    "concept": "有状态 Agent 用 StateGraph 管理上下文。" * 4,
                    "keyPoint": (
                        "- 定义StateGraph状态Schema，明确节点间传递的数据结构\n"
                        "- 注册节点函数，实现具体业务逻辑\n"
                        "- 配置条件边，实现分支与循环\n"
                        "- 接入Checkpointer，支持状态持久化与中断恢复"
                    ),
                    "example": "用 SqliteSaver 跑通一次中断恢复。" * 3,
                    "flow": ["定义State…", "注册节点函数实…", "配置条件边实现…", "接入Check…"],
                }
            ],
        },
        ["岗"],
        rich_journal=True,
    )
    assert "LangGraph" in out["cover"]["title"]
    assert not out["cover"]["title"].endswith("…")
    assert "LangChain" in out["knowledge"][0]["topicTitle"]
    flow = out["knowledge"][0]["flow"]
    assert flow
    assert all("…" not in s for s in flow)
    assert flow[0] == "定义StateGraph"
    assert any("Checkpointer" in s for s in flow)


ROOT = Path(__file__).resolve().parents[2]


def test_card_handoff_copy_uses_research_then_compose():
    paths = [
        ROOT / "src/cn_social_agent/agent/loop.py",
        ROOT / "src/cn_social_agent/tools/builtin.py",
        ROOT / "src/cn_social_agent/cards/categories.py",
        ROOT / "src/cn_social_agent/workbench/index.html",
        ROOT / "src/cn_social_agent/workbench/cards_workshop.js",
    ]
    combined = "\n".join(p.read_text(encoding="utf-8") for p in paths)
    assert "扫描并生成" not in combined
    assert "深采" in combined
    assert "成刊" in combined


def test_cards_workshop_warns_before_exporting_degraded_compose():
    js = (
        ROOT / "src/cn_social_agent/workbench/cards_workshop.js"
    ).read_text(encoding="utf-8")
    assert "qualityWarning" in js
    assert "成刊已降级" in js
    assert "仍要强制导出" in js or "仍要导出" in js
    assert "qualityGatePass" in js or "quality_gate_pass" in js


def test_history_badges_distinguish_research_journal_cached():
    js = (
        ROOT / "src/cn_social_agent/workbench/cards_workshop.js"
    ).read_text(encoding="utf-8")
    assert "historyModeBadge" in js
    assert '"research"' in js or "'research'" in js
    assert "深采" in js
    assert "降级" in js
    # research drafts must not be labeled as legacy「内置」
    assert 'h.mode === "ai" ? "AI"' not in js


def test_llm_teach_targets_rich_journal_card_count():
    from cn_social_agent.cards.categories import CATEGORIES

    for cat in CATEGORIES.values():
        teach = cat.get("llm_teach") or ""
        goal = cat.get("llm_goal") or ""
        blob = f"{teach}\n{goal}"
        assert "5" in blob and "6" in blob
        assert "3 张" not in goal
        assert "80–110" not in teach


def test_present_artifact_dock_reads_card_id():
    html = (ROOT / "src/cn_social_agent/workbench/index.html").read_text(
        encoding="utf-8"
    )
    assert "data.card_id || data.history_id || data.id" in html


def test_evidence_list_renders_source_link():
    js = (
        ROOT / "src/cn_social_agent/workbench/cards_workshop.js"
    ).read_text(encoding="utf-8")
    assert "kc-ev-link" in js
    assert "e.url" in js or "e.title" in js


def test_rich_journal_does_not_pad_silent_theme_cards():
    from cn_social_agent.cards.build import normalize_llm_payload

    out = normalize_llm_payload(
        {
            "cover": {"title": "短刊", "description": "导语" * 20},
            "knowledge": [
                {
                    "topicTitle": "仅两张",
                    "concept": "x" * 40,
                    "keyPoint": "- a\n- b\n- c",
                    "example": "y" * 30,
                },
                {
                    "topicTitle": "第二张",
                    "concept": "x" * 40,
                    "keyPoint": "- a\n- b\n- c",
                    "example": "y" * 30,
                },
            ],
        },
        ["主题"],
        rich_journal=True,
    )
    assert len(out["knowledge"]) == 2
    assert all(not k.get("paddedFromTheme") for k in out["knowledge"])


def test_incomplete_cards_mark_padded_from_theme():
    from cn_social_agent.cards.build import normalize_llm_payload

    out = normalize_llm_payload(
        {
            "cover": {"title": "测试", "description": "导语足够长用于封面描述展示", "tags": ["a"]},
            "knowledge": [{"topicTitle": "空壳标题一"}],
        },
        ["岗"],
    )
    assert out["knowledge"][0].get("paddedFromTheme") is True


def test_category_signals_keep_product_snippets():
    from cn_social_agent.cards.evidence import build_pack, is_useful_snippet

    product_line = (
        "产品功能上手教程：用户痛点是口播耗时，亮点是一键大纲，适用边界是无素材空镜"
    )
    assert is_useful_snippet(product_line, category="product_explain")
    # Hiring-biased filter should be weaker for pure product copy without JD terms
    pack = build_pack(
        [{"text": product_line, "role": "口播", "query": "q", "engine": "bing"}],
        category="product_explain",
    )
    assert pack["count"] >= 1


def test_propose_handoff_passes_category():
    html = (ROOT / "src/cn_social_agent/workbench/index.html").read_text(
        encoding="utf-8"
    )
    assert "ws.setCategory(cat)" in html or "ws.setCategory(category)" in html
    assert "inferCardCategory" in html
    assert "resultData.category || args.category" in html
    js = (
        ROOT / "src/cn_social_agent/workbench/cards_workshop.js"
    ).read_text(encoding="utf-8")
    assert "模板补全" in js
    assert "QualityPanel" in js or "qualityGatePass" in js
    qp = (ROOT / "src/cn_social_agent/workbench/quality_panel.js").read_text(
        encoding="utf-8"
    )
    assert "classifyError" in qp
    assert "fromJournalDepth" in qp
    assert "presQualityPanel" in html or "kcQualityPanel" in html
    assert "presNowDo" in html
    assert "jobActionError" in html
    assert "shellNext" not in html
    assert "kcHistFold" in html
    assert 'aside class="rail"' in html or 'aside class="rail"' in html.replace("'", '"')


def test_keypoint_list_and_broken_repr_recover():
    from cn_social_agent.cards.build import coerce_points, normalize_llm_payload

    # LLM returned keyPoint as a real list
    assert coerce_points(["- a", "b", "- c"]) == ["a", "b", "c"]
    # Truncated Python list-repr string nested inside keyPoint
    broken = "- ['- Naive RAG：单步检索+拼接，召回率低', '- 多粒度检索：文档级/段落级/句子级', '-…"
    pts = coerce_points(broken)
    assert pts == ["Naive RAG：单步检索+拼接，召回率低", "多粒度检索：文档级/段落级/句子级"]

    out = normalize_llm_payload(
        {
            "cover": {"title": "RAG 全景", "description": "导语" * 10},
            "knowledge": [
                {
                    "topicTitle": "RAG 方案谱系",
                    "card_kind": "keypoints",
                    "concept": "检索增强生成把回答钉在语料上。" * 4,
                    "keyPoint": broken,
                    "example": "接入制度库后先命中条款再生成。" * 2,
                }
            ],
        },
        ["RAG"],
        rich_journal=True,
    )
    real = out["knowledge"][0]["realPoints"]
    assert real == ["Naive RAG：单步检索+拼接，召回率低", "多粒度检索：文档级/段落级/句子级"]
    assert all("['" not in p and "…" not in p for p in real)
    assert "['" not in out["knowledge"][0]["keyPoint"]


def test_infer_card_kind_and_xhs_caption():
    from cn_social_agent.cards.styles import infer_card_kind
    from cn_social_agent.platforms.xiaohongshu.publisher import build_xhs_caption

    assert infer_card_kind({"topicTitle": "A vs B", "concept": "对比误区"}) == "compare"
    assert infer_card_kind({"concept": "召回率提升 35%", "keyPoint": "指标"}) == "data"
    assert infer_card_kind({"card_kind": "quote", "concept": "长文本也不改"}) == "quote"
    cap = build_xhs_caption(
        title="Agent · RAG",
        cover={"description": "三张卡片拆解编排", "tags": ["Agent", "RAG"]},
        knowledge=[{"topicTitle": "编排"}, {"topicTitle": "检索"}],
        brand_signature="CN Workbench",
    )
    assert "编排" in cap["caption"]
    assert "#知识卡片" in cap["hashtags"]
    assert cap["creator_url"].startswith("https://creator.xiaohongshu.com")


@pytest.mark.asyncio
async def test_xiaohongshu_publisher_half_auto(tmp_path):
    from cn_social_agent.platforms import get_publisher, list_platforms

    assert "xiaohongshu" in list_platforms()
    pub = get_publisher("xiaohongshu")
    st = await pub.status(user_id="u1")
    assert st["ready"] and st.get("half_auto")
    img = tmp_path / "c.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    r = await pub.publish(
        user_id="u1",
        title="测试标题",
        image_paths=[img],
        direct=False,
        meta={
            "cover": {"description": "导语", "tags": ["AI"]},
            "knowledge": [{"topicTitle": "概念卡"}],
            "brand_signature": "签名",
        },
    )
    assert r["status"] == "draft"
    assert r.get("half_auto")
    assert "概念卡" in (r.get("caption") or "")


def test_normalize_fills_incomplete_cards():
    from cn_social_agent.cards.build import normalize_llm_payload

    out = normalize_llm_payload(
        {
            "cover": {"title": "测试", "description": "导语足够长用于封面描述展示", "tags": ["a", "b", "c"]},
            "knowledge": [
                {"topicTitle": "空壳标题一"},  # title only
                {
                    "topicTitle": "工具调用",
                    "concept": "工具调用是Agent将LLM输出转化为外部动作的核心机制，通过函数注册暴露业务逻辑。",
                    "keyPoint": "- 【机制】匹配schema并执行\n- 【易错】描述过简\n- 【检验】边界case",
                    "example": "候选人演示工具路由与参数校验日志。",
                    "flow": ["匹配", "执行", "回传"],
                },
                {"topicTitle": "空壳标题三", "concept": "太短"},
            ],
        },
        ["岗"],
    )
    assert len(out["knowledge"]) == 3
    assert len(out["knowledge"][0]["concept"]) >= 24
    assert len(out["knowledge"][0]["realPoints"]) >= 2
    assert len(out["knowledge"][2]["concept"]) >= 24
    assert out["knowledge"][1]["flow"]


def test_history_per_user(tmp_path, monkeypatch):
    import cn_social_agent.cards.history as hist

    monkeypatch.setattr(hist, "history_dir", lambda: tmp_path)
    rec_a = save_history_record(
        {
            "cover": {"title": "A", "gradientPart": "g"},
            "knowledge": [{"topicTitle": "t1"}],
            "mode": "cached",
            "snippetCount": 0,
            "sources": [],
            "roles": ["r"],
        },
        user_id="user_a",
        email="a@test.com",
    )
    save_history_record(
        {
            "cover": {"title": "B", "gradientPart": "g2"},
            "knowledge": [{"topicTitle": "t2"}],
            "mode": "ai",
            "snippetCount": 1,
            "sources": [],
            "roles": ["r2"],
        },
        user_id="user_b",
        email="b@test.com",
    )
    assert rec_a["id"]
    summaries_a = list_history_summaries(user_id="user_a", email="a@test.com")
    summaries_b = list_history_summaries(user_id="user_b", email="b@test.com")
    assert summaries_a[0]["title"] == "A"
    assert summaries_b[0]["title"] == "B"
    assert get_history_item(rec_a["id"], user_id="user_a", email="a@test.com")
    assert get_history_item(rec_a["id"], user_id="user_b", email="b@test.com") is None
    assert delete_history_item(rec_a["id"], user_id="user_a", email="a@test.com") is True
    assert list_history_summaries(user_id="user_a", email="a@test.com") == []
    assert delete_history_item(rec_a["id"], user_id="user_a", email="a@test.com") is False


def test_history_email_key_stable_and_migrates_orphans(tmp_path, monkeypatch):
    import cn_social_agent.cards.history as hist

    monkeypatch.setattr(hist, "history_dir", lambda: tmp_path)
    orphan = tmp_path / "u_randomold.json"
    orphan.write_text(
        '[{"id":"h1","ts":"2026-01-01T00:00:00Z","cover":{"title":"旧记录","gradientPart":"g"},'
        '"knowledge":[{"topicTitle":"t"}],"mode":"ai","user_id":"u_randomold"}]',
        encoding="utf-8",
    )
    rows = list_history_summaries(user_id="u_demo_local", email="demo@local.test")
    assert any(r["title"] == "旧记录" for r in rows)
    # Second load uses consolidated email file
    assert (tmp_path / "e_demo_at_local.test.json").is_file() or any(
        p.name.startswith("e_demo") for p in tmp_path.glob("e_*.json")
    )


def test_close_truncated_json_and_parse():
    from cn_social_agent.cards.llm import _close_truncated_json, _parse_json_content
    from cn_social_agent.cards.build import normalize_llm_payload

    truncated = """{
  "cover": {
    "title": "AI招聘能力图谱",
    "description": "聚焦三大岗位",
    "tags": [
      "AI招聘",
      "Agent"
"""
    closed = _close_truncated_json(truncated)
    data = json.loads(closed)
    assert data["cover"]["title"] == "AI招聘能力图谱"
    assert "Agent" in data["cover"]["tags"]

    # Mid-cut with knowledge started
    messy = (
        '{\n "cover": {"title": "T", "description": "D", "tags": ["a"]},\n'
        ' "knowledge": [\n'
        '  {"topicTitle": "主题", "concept": "概念", "keyPoint": "- a\\n- b\\n- c", "example": "例"}\n'
        # missing closing
    )
    parsed = _parse_json_content(messy)
    assert parsed["cover"]["title"] == "T"

    # Real failure: cut mid-key name after topicTitle
    mid_key = (
        '{"cover":{"title":"AI工程师招聘洞察","description":"三张能力卡片",'
        '"tags":["AI招聘","Agent开发","RAG工程"]},'
        '"knowledge":[{"topicTitle":"智能体编排能力","conc'
    )
    recovered = _parse_json_content(mid_key)
    assert recovered["cover"]["title"] == "AI工程师招聘洞察"
    assert recovered["knowledge"][0]["topicTitle"] == "智能体编排能力"
    norm = normalize_llm_payload(recovered, ["岗"])
    assert len(norm["knowledge"]) == 3
    assert norm["knowledge"][0]["topicTitle"] == "智能体编排能力"


def test_card_tools_registered_and_produce_mode():
    reg = ToolRegistry()
    register_builtin_tools(reg)
    names = {t["name"] for t in reg.list_tools()}
    assert "propose_knowledge_cards" in names
    assert "scan_knowledge_cards" in names
    assert "present_knowledge_card" in names
    assert "propose_knowledge_cards" in PRODUCE_TOOLS
    assert detect_mode([{"role": "user", "content": "帮我做一组知识卡片"}]) == "produce"


@pytest.mark.asyncio
async def test_card_tool_handlers():
    p = await tool_propose_knowledge_cards(
        "岗A、岗B", topic="DeepSeek", category="industry_brief"
    )
    assert p["propose_cards"] and p["roles"] == ["岗A", "岗B"]
    assert p["topic"] == "DeepSeek"
    assert p["category"] == "industry_brief"
    s = await tool_scan_knowledge_cards("岗A", category="product_explain")
    assert s["scan_cards"] and s["roles"] == ["岗A"]
    assert s["category"] == "product_explain"
    pr = await tool_present_knowledge_card("h123", title="T")
    assert pr["present"] and pr["card_id"] == "h123"


@pytest.mark.asyncio
async def test_propose_infers_product_category_not_hiring():
    """Grok Build-style topics must not fall back to 招聘洞察."""
    p = await tool_propose_knowledge_cards(
        roles="",
        topic="Grok Build 开源 Agentic CLI",
        note="9 天 2 万 Star，安装上手与安全风险",
    )
    assert p["category"] == "product_explain"
    assert p["roles"], "expected at least one role seed"
    assert "Grok" in "、".join(p["roles"])
    assert "开发工程师" not in "、".join(p["roles"])


def test_infer_category_rules():
    from cn_social_agent.cards.categories import infer_category

    assert infer_category("AI Agent 开发工程师招聘 JD") == "hiring_insight"
    assert infer_category("Grok Build 开源 CLI 工具 GitHub Star") == "product_explain"
    assert infer_category("Agent 工程学习路线 从零入门") == "skill_roadmap"
    assert infer_category("AI 赛道融资与竞争格局周报") == "industry_brief"
    assert infer_category("") == ""


@pytest.mark.asyncio
async def test_cards_redirect_and_scan(monkeypatch):
    from aiohttp.test_utils import TestClient, TestServer

    from cn_social_agent.api import create_app

    monkeypatch.setenv("WORKBENCH_STORE", "memory")
    monkeypatch.setenv("WORKBENCH_LLM", "mock")
    app = create_app()
    async with TestClient(TestServer(app)) as client:
        r = await client.get("/cards", allow_redirects=False)
        assert r.status in (301, 302, 303, 307)
        assert "mode=card" in (r.headers.get("Location") or "")

        login = await client.post(
            "/api/auth/login",
            json={"email": "demo@local.test", "password": "demo123456"},
        )
        assert login.status == 200
        token = (await login.json())["accessToken"]
        headers = {"Authorization": f"Bearer {token}"}

        scan = await client.post(
            "/api/cards/scan",
            json={"roles": ["测试岗"]},
            headers=headers,
        )
        assert scan.status == 200
        body = await scan.json()
        assert body.get("id")
        assert body.get("cover")
        assert body.get("knowledge")

        hist = await client.get("/api/cards/history", headers=headers)
        assert hist.status == 200
        rows = await hist.json()
        assert any(row["id"] == body["id"] for row in rows)

        deleted = await client.delete(
            f"/api/cards/history/{body['id']}", headers=headers
        )
        assert deleted.status == 200
        rows2 = await (await client.get("/api/cards/history", headers=headers)).json()
        assert all(row["id"] != body["id"] for row in rows2)

        js = await client.get("/static/cards_workshop.js")
        assert js.status == 200

        cats = await client.get("/api/cards/categories", headers=headers)
        assert cats.status == 200
        body_c = await cats.json()
        assert len(body_c.get("categories") or []) >= 4
