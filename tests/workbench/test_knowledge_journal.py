from typing import Any
from unittest.mock import AsyncMock

import pytest

from cn_social_agent.cards.evidence import (
    build_pack,
    merge_packs,
    selected_evidences,
    validate_evidence_ids,
)


def test_build_pack_assigns_ids_and_sorts():
    raw = [
        {"text": "招聘 AI Agent 工程师要求 LangGraph 编排与工具调用经验三年", "role": "AI Agent 开发工程师", "query": "q1", "engine": "bing"},
        {"text": "独立（拼音：dú lì），汉语词语", "role": "独立开发者", "query": "q2", "engine": "baidu"},
    ]
    pack = build_pack(raw, limit=40)
    assert all(e["id"].startswith("e") for e in pack["evidences"])
    assert all("拼音" not in e["text"] for e in pack["evidences"])
    assert pack["evidences"][0]["score"] >= pack["evidences"][-1]["score"]


def test_build_pack_preserves_url_and_title():
    pack = build_pack(
        [
            {
                "text": "招聘岗位要求掌握 RAG 向量检索与重排，独立交付知识库问答系统",
                "role": "R",
                "query": "q",
                "engine": "bing",
                "url": "https://example.com/jd/rag",
                "title": "RAG 工程师 JD",
            }
        ]
    )
    row = pack["evidences"][0]
    assert row["url"] == "https://example.com/jd/rag"
    assert row["title"] == "RAG 工程师 JD"


def test_extract_result_rows_parses_bing_algo():
    from cn_social_agent.cards.scrape import extract_result_rows

    html = """
    <ol id="b_results">
      <li class="b_algo">
        <h2><a href="https://jobs.example.com/agent">Agent 开发工程师招聘</a></h2>
        <div class="b_caption"><p>岗位职责含 LangGraph 编排、工具调用与 RAG 检索交付经验三年以上</p></div>
      </li>
      <li class="b_algo">
        <h2><a href="https://wiki.example.com/noise">汉语词语</a></h2>
        <div class="b_caption"><p>独立（拼音：dú lì），名词、动词</p></div>
      </li>
    </ol>
    """
    rows = extract_result_rows(html)
    assert rows
    assert rows[0]["url"].startswith("https://jobs.example.com/")
    assert "Agent" in rows[0]["title"]
    assert "LangGraph" in rows[0]["text"]


def test_extract_sogou_result_rows_parses_vrwrap():
    from cn_social_agent.cards.scrape import extract_sogou_result_rows

    html = """
    <div class="results">
      <div class="vrwrap">
        <h3 class="vr-title"><a href="/link?url=abc123">AI Agent 开发工程师招聘</a></h3>
        <div class="text-layout">岗位职责：负责 LangGraph 编排、RAG 检索与工具调用，三年以上工程经验</div>
      </div>
      <div class="vrwrap">
        <h3 class="vr-title"><a href="https://blog.example.com/post">工程实践分享</a></h3>
        <div class="text-layout">Agent 系统的可观测性与失败回退设计，附带真实踩坑案例与部署经验总结</div>
      </div>
    </div>
    <div id="page"></div>
    """
    rows = extract_sogou_result_rows(html)
    assert len(rows) == 2
    assert rows[0]["url"].startswith("https://www.sogou.com/link?url=")
    assert "招聘" in rows[0]["title"]
    assert rows[1]["url"] == "https://blog.example.com/post"


def test_filter_rows_drops_ad_nav_domains():
    from cn_social_agent.cards.scrape import filter_rows

    rows = [
        {
            "text": "AI工具集官网收录了国内外数百个AI工具方便查找使用的导航大全网站",
            "url": "https://ai-bot.cn/",
        },
        {
            "text": "招聘岗位职责含 LangGraph 编排、工具调用与 RAG 检索交付经验三年以上",
            "url": "https://jobs.example.com/agent",
        },
    ]
    kept = filter_rows(rows, role="AI Agent 开发工程师", limit=10)
    assert len(kept) == 1
    assert kept[0]["url"] == "https://jobs.example.com/agent"


def test_describe_scan_stats_explains_dead_engines():
    from cn_social_agent.cards.scrape import describe_scan_stats

    stats = [
        {
            "sogou": {"pages": 2, "raw": 0, "empty": 2},
            "bing": {"pages": 3, "raw": 24, "empty": 0},
            "raw_total": 24,
            "kept": 0,
        }
    ]
    msg = describe_scan_stats(stats)
    assert "搜狗返回空结果" in msg
    assert "必应抓到 24 条" in msg
    assert "百度不可达/超时" in msg


def test_clean_snippet_keeps_csdn_article_but_strips_suffix():
    from cn_social_agent.cards.evidence import clean_snippet_text, looks_like_serp_noise

    t = "Agent 已经从热门概念变成正式岗位，全球公开招聘岗位接近 9 万个-CSDN博客"
    cleaned = clean_snippet_text(t)
    assert not looks_like_serp_noise(cleaned)
    assert "CSDN" not in cleaned
    assert "9 万个" in cleaned


def test_merge_and_filter_selected():
    a = build_pack([{"text": "招聘岗位职责含 RAG 向量检索与重排经验要求", "role": "R", "query": "q", "engine": "bing"}])
    b = build_pack([{"text": "面试考察 LangGraph 状态机与失败回退交付物", "role": "R", "query": "q2", "engine": "bing"}])
    m = merge_packs(a, b)
    assert len(m["evidences"]) >= 2
    m["evidences"][0]["selected"] = False
    sel = selected_evidences(m)
    assert all(e.get("selected", True) for e in sel)


def test_merge_packs_preserves_existing_ids_and_allocates_new_ids():
    a = build_pack(
        [
            {
                "text": "招聘岗位职责含 RAG 向量检索与重排经验要求",
                "role": "R",
                "query": "q1",
                "engine": "bing",
            },
            {
                "text": "面试考察 Agent 工具调用与失败回退交付物",
                "role": "R",
                "query": "q2",
                "engine": "bing",
            },
        ]
    )
    old_ids = {e["text"]: e["id"] for e in a["evidences"]}
    a["evidences"][0]["selected"] = False
    b = build_pack(
        [
            {
                "text": "工程师岗位要求模型训练推理与部署优化经验",
                "role": "R",
                "query": "q3",
                "engine": "bing",
            }
        ]
    )

    merged = merge_packs(a, b)
    by_text = {e["text"]: e for e in merged["evidences"]}

    assert all(by_text[text]["id"] == eid for text, eid in old_ids.items())
    assert by_text[a["evidences"][0]["text"]]["selected"] is False
    new_row = by_text[b["evidences"][0]["text"]]
    assert new_row["id"] not in set(old_ids.values())


def test_validate_evidence_ids_drops_fake_and_backfills():
    pack = build_pack([{"text": "招聘 JD 要求 Agent 工具调用与编排能力三年经验", "role": "A", "query": "q", "engine": "bing"}])
    eid = pack["evidences"][0]["id"]
    ids = validate_evidence_ids(["nope", eid], pack, card_text="工具调用 编排")
    assert eid in ids
    assert "nope" not in ids

    ids = validate_evidence_ids(["nope"], pack, card_text="工具调用 编排")
    assert ids and ids[0] in {e["id"] for e in pack["evidences"]}
    assert "nope" not in ids


def test_validate_evidence_ids_ignores_deselected():
    a = build_pack(
        [{"text": "招聘岗位职责含 RAG 向量检索与重排经验要求三年", "role": "R", "query": "q", "engine": "bing"}]
    )
    b = build_pack(
        [{"text": "面试考察 LangGraph 状态机与失败回退交付物经验", "role": "R", "query": "q2", "engine": "bing"}]
    )
    pack = merge_packs(a, b)
    assert len(pack["evidences"]) >= 2
    deselected = pack["evidences"][0]
    selected = pack["evidences"][1]
    deselected["selected"] = False
    selected["selected"] = True

    ids = validate_evidence_ids(
        [deselected["id"]], pack, card_text="向量检索 重排 LangGraph 状态机"
    )
    assert deselected["id"] not in ids
    assert selected["id"] in ids

    for e in pack["evidences"]:
        e["selected"] = False
    assert validate_evidence_ids([deselected["id"], selected["id"]], pack) == []
    assert validate_evidence_ids(["nope"], pack, card_text="工具调用") == []


def test_build_queries_deep_vs_shallow():
    from cn_social_agent.cards.scrape import build_queries

    shallow = build_queries("AI Agent 开发工程师", category="hiring_insight", depth="shallow")
    deep = build_queries("AI Agent 开发工程师", category="hiring_insight", depth="deep")
    assert 1 <= len(shallow) <= 3
    assert 6 <= len(deep) <= 10
    # Shallow keeps quoted role; deep mixes quoted and unquoted
    assert any('"' in q for q in shallow)
    assert any('"' not in q for q in deep)


def test_deep_queries_follow_topic_not_hardcoded_stack():
    """Every deep query must mention the topic; no baked-in technology."""
    from cn_social_agent.cards.scrape import build_queries

    topic = "DeepSeek MLA MoE 架构"
    deep = build_queries(topic, category="hiring_insight", depth="deep")
    assert deep
    assert all(topic in q for q in deep)
    # A DeepSeek request must never search a stack the user did not ask for
    assert not any("LangGraph" in q or "RAG" in q for q in deep)

    other = build_queries("独立开发者", category="hiring_insight", depth="deep")
    assert not any("LangGraph" in q or "RAG" in q for q in other)


def test_extract_short_topic_cuts_long_headline():
    from cn_social_agent.cards.topic import extract_short_topic

    title = "浏览器扩展合集：我们为你找到了这 6 款实用、有趣的「新玩意」"
    assert extract_short_topic(title) == "浏览器扩展合集"
    assert extract_short_topic("Grok Build") == "Grok Build"


def test_build_search_terms_uses_short_subject():
    from cn_social_agent.cards.topic import build_search_terms

    terms = build_search_terms("浏览器扩展合集：我们为你找到了这 6 款「新玩意」")
    assert terms
    assert "浏览器扩展合集" in terms
    assert not any("我们为你" in t for t in terms)


def test_is_topic_relevant_rejects_offtopic():
    from cn_social_agent.cards.topic import is_topic_relevant, topic_terms

    tt = topic_terms("浏览器扩展合集")
    assert is_topic_relevant("十款 Chrome 扩展帮你提升前端开发效率", tt)
    assert is_topic_relevant("Multi-highlight 是一款网页高亮浏览器扩展", tt)
    assert not is_topic_relevant("2026年AI写论文工具怎么选六款实测打分", tt)
    assert not is_topic_relevant("荣耀X40 手机 118 万次浏览", tt)


def test_seed_evidences_from_notes_skips_meta_lines():
    from cn_social_agent.cards.topic import seed_evidences_from_notes

    notes = (
        "为何值得做：好玩\n来源：少数派\n链接：https://x\n\n"
        "Multi-highlight 是一款网页高亮浏览器扩展，可以批量高亮关键词并保存，方便资料研究。"
    )
    seeds = seed_evidences_from_notes(notes, topic="浏览器扩展合集", source="少数派")
    assert len(seeds) == 1
    assert seeds[0]["engine"] == "seed"
    assert not any(s["text"].startswith("为何值得做") for s in seeds)


@pytest.mark.asyncio
async def test_run_research_seeds_from_notes_skip_scrape_when_rich(monkeypatch):
    from cn_social_agent.cards import service as svc

    scan = AsyncMock(side_effect=AssertionError("should not scrape when seeds are rich"))
    monkeypatch.setattr(svc, "scan_roles", scan)
    notes = "\n".join(
        f"扩展{i} 是一款浏览器扩展，可以帮助整理标签页与高亮网页内容，提升信息研究效率的实用工具。"
        for i in range(6)
    )
    out = await svc.run_research(
        ["浏览器扩展合集"],
        category="product_explain",
        depth="deep",
        persist=False,
        research_notes=notes,
    )
    assert out["ok"] is True
    assert out["evidencePack"]["count"] >= 5
    assert all(e["engine"] == "seed" for e in out["evidencePack"]["evidences"])
    scan.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_research_gates_offtopic_topup(monkeypatch):
    from cn_social_agent.cards import service as svc

    fake_rows = [[
        {"text": "十款 Chrome 扩展帮你提升前端开发效率与调试体验", "engine": "bing", "role": "浏览器扩展合集"},
        {"text": "2026年AI写论文工具怎么选六款实测打分对比", "engine": "bing", "role": "浏览器扩展合集"},
        {"text": "荣耀X40 手机评测 118 万次浏览热议", "engine": "bing", "role": "浏览器扩展合集"},
    ]]
    monkeypatch.setattr(svc, "scan_roles", AsyncMock(return_value=fake_rows))
    out = await svc.run_research(
        ["浏览器扩展合集"], category="product_explain", depth="deep", persist=False
    )
    texts = [e["text"] for e in out["evidencePack"]["evidences"]]
    assert any("Chrome 扩展" in t for t in texts)
    assert not any("写论文" in t for t in texts)
    assert not any("荣耀X40" in t for t in texts)


@pytest.mark.asyncio
async def test_run_research_builds_pack(monkeypatch):
    from cn_social_agent.cards import service as svc

    fake_rows = [[
        {
            "text": "招聘 AI Agent 岗位职责含 LangGraph 与工具调用三年经验",
            "query": "q",
            "engine": "bing",
            "role": "AI Agent 开发工程师",
        },
    ]]
    monkeypatch.setattr(svc, "scan_roles", AsyncMock(return_value=fake_rows))
    out = await svc.run_research(
        ["AI Agent 开发工程师"], category="hiring_insight", depth="deep"
    )
    assert out["mode"] == "research"
    assert out["evidencePack"]["count"] >= 1
    assert out["packId"] or out.get("id")


@pytest.mark.asyncio
async def test_run_research_append_reuses_history_id(monkeypatch):
    from cn_social_agent.cards import cloud
    from cn_social_agent.cards import service as svc

    fake_rows = [[
        {
            "text": "工程师岗位要求模型训练推理与部署优化经验三年",
            "query": "q",
            "engine": "bing",
            "role": "模型工程师",
        },
    ]]
    saved_records: list[dict[str, Any]] = []

    def fake_save(rec, **kwargs):
        saved_records.append(dict(rec))
        return rec

    monkeypatch.setattr(svc, "scan_roles", AsyncMock(return_value=fake_rows))
    monkeypatch.setattr(svc, "save_history_record", fake_save)
    monkeypatch.setattr(cloud, "upsert_card_record", AsyncMock(return_value=True))

    out = await svc.run_research(
        ["模型工程师"],
        category="hiring_insight",
        depth="deep",
        append_history_id="h_existing",
    )

    assert saved_records[0]["id"] == "h_existing"
    assert out["id"] == "h_existing"
    assert out["packId"] == "h_existing"


def test_normalize_allows_4_to_6_cards_and_evidence_ids():
    from cn_social_agent.cards.build import normalize_llm_payload

    pack = {
        "evidences": [
            {
                "id": "e1",
                "text": "招聘要求 LangGraph 编排与工具调用三年经验岗位职责",
                "score": 3,
                "selected": True,
            }
        ]
    }
    parsed = {
        "cover": {
            "title": "测试刊",
            "description": "读者将学会具名编排与检验标准的评估方法一二三四",
        },
        "knowledge": [
            {
                "topicTitle": "编排",
                "card_kind": "steps",
                "concept": "用状态机做工具调用与编排，失败可回退。" * 2,
                "keyPoint": "- a\n- b\n- c",
                "example": "y" * 30,
                "flow": ["a", "b", "c"],
                "evidenceIds": ["e1", "fake"],
            },
            {
                "topicTitle": "检索",
                "card_kind": "keypoints",
                "concept": "岗位要求强调向量检索与重排经验。" * 2,
                "keyPoint": "- a\n- b",
                "example": "y" * 30,
                "evidenceIds": ["e1"],
            },
            {
                "topicTitle": "交付",
                "card_kind": "data",
                "concept": "招聘 JD 用可观测指标衡量 Agent 交付。" * 2,
                "keyPoint": "- a",
                "example": "y" * 30,
                "metric": "p95",
                "evidenceIds": [],
            },
            {
                "topicTitle": "对比",
                "card_kind": "compare",
                "concept": "只调 API 不如状态机编排稳。" * 2,
                "keyPoint": "- a",
                "example": "y" * 30,
                "compare": {"left": "只调API", "right": "状态机"},
                "evidenceIds": ["e1"],
            },
        ],
    }
    out = normalize_llm_payload(
        parsed, ["AI Agent"], category="hiring_insight", evidence_pack=pack
    )
    assert 3 <= len(out["knowledge"]) <= 6
    assert len(out["knowledge"]) >= 4
    for k in out["knowledge"]:
        assert k.get("evidenceIds")
        assert "fake" not in k["evidenceIds"]


@pytest.mark.asyncio
async def test_compose_with_llm_uses_evidence_ids(monkeypatch):
    from cn_social_agent.cards import llm as llm_mod

    pack = {
        "evidences": [
            {
                "id": "e1",
                "text": "招聘要求 LangGraph 编排与工具调用三年经验岗位职责",
                "score": 3,
                "selected": True,
            }
        ]
    }
    outline = {
        "cover": {
            "title": "测试刊",
            "description": "读者将学会具名编排与检验标准的评估方法一二三四",
            "tags": ["编排", "检索", "交付"],
        },
        "knowledge": [
            {
                "topicTitle": "编排",
                "angle": "流程型",
                "card_kind": "steps",
                "evidenceIds": ["e1"],
            },
            {
                "topicTitle": "检索",
                "angle": "定义型",
                "card_kind": "keypoints",
                "evidenceIds": ["e1"],
            },
            {
                "topicTitle": "交付",
                "angle": "数据型",
                "card_kind": "data",
                "evidenceIds": ["e1"],
            },
        ],
    }
    expanded = {
        "knowledge": [
            {
                "topicTitle": "编排",
                "card_kind": "steps",
                "concept": "x" * 40,
                "keyPoint": "- a\n- b\n- c",
                "example": "y" * 30,
                "flow": ["a", "b", "c"],
                "evidenceIds": ["e1"],
            },
            {
                "topicTitle": "检索",
                "card_kind": "keypoints",
                "concept": "x" * 40,
                "keyPoint": "- a\n- b",
                "example": "y" * 30,
                "evidenceIds": ["e1"],
            },
            {
                "topicTitle": "交付",
                "card_kind": "data",
                "concept": "x" * 40,
                "keyPoint": "- a\n- b",
                "example": "y" * 30,
                "metric": "p95",
                "evidenceIds": ["e1"],
            },
        ]
    }
    calls = {"n": 0}

    async def fake_complete_json(**kwargs):
        calls["n"] += 1
        return outline if calls["n"] == 1 else expanded

    monkeypatch.setattr(llm_mod, "_complete_json", fake_complete_json)
    out = await llm_mod.compose_with_llm(
        ["AI Agent"], evidence_pack=pack, category="hiring_insight"
    )
    assert 3 <= len(out["knowledge"]) <= 6
    for k in out["knowledge"]:
        assert k.get("evidenceIds")
        assert "e1" in k["evidenceIds"]
        assert k.get("stance") == "evidence"


@pytest.mark.asyncio
async def test_run_compose_attaches_pack(monkeypatch):
    from cn_social_agent.cards import service as svc
    from cn_social_agent.cards.build import normalize_llm_payload
    from cn_social_agent.cards.evidence import build_pack

    pack = build_pack(
        [
            {
                "text": "招聘岗位要求 RAG 与向量检索重排经验三年任职",
                "role": "R",
                "query": "q",
                "engine": "bing",
            }
        ]
    )

    async def fake_compose(*a, **k):
        return normalize_llm_payload(
            {
                "cover": {"title": "T", "description": "d" * 40},
                "knowledge": [
                    {
                        "topicTitle": "A",
                        "concept": "c" * 40,
                        "keyPoint": "- a\n- b\n- c",
                        "example": "e" * 30,
                        "evidenceIds": [pack["evidences"][0]["id"]],
                    },
                    {
                        "topicTitle": "B",
                        "concept": "c" * 40,
                        "keyPoint": "- a\n- b\n- c",
                        "example": "e" * 30,
                        "evidenceIds": [pack["evidences"][0]["id"]],
                    },
                    {
                        "topicTitle": "C",
                        "concept": "c" * 40,
                        "keyPoint": "- a\n- b\n- c",
                        "example": "e" * 30,
                        "evidenceIds": [pack["evidences"][0]["id"]],
                    },
                ],
            },
            ["R"],
            evidence_pack=pack,
        )

    monkeypatch.setattr(svc, "compose_with_llm", fake_compose)
    out = await svc.run_compose(
        roles_raw=["R"], evidence_pack=pack, use_workbench_llm=False
    )
    assert out["mode"] == "journal"
    assert out["evidencePack"]["count"] >= 1
    assert all(k.get("evidenceIds") for k in out["knowledge"])


@pytest.mark.asyncio
async def test_run_compose_llm_fail_forces_cached(monkeypatch):
    from cn_social_agent.cards import service as svc
    from cn_social_agent.cards.evidence import build_pack

    pack = build_pack(
        [
            {
                "text": "招聘岗位要求 RAG 与向量检索重排经验三年任职",
                "role": "R",
                "query": "q",
                "engine": "bing",
            }
        ]
    )

    async def boom(*a, **k):
        raise RuntimeError("llm down")

    monkeypatch.setattr(svc, "compose_with_llm", boom)
    out = await svc.run_compose(
        roles_raw=["R"], evidence_pack=pack, use_workbench_llm=False, persist=False
    )
    assert out["mode"] == "cached"
    assert out["evidencePack"]["count"] >= 1
    assert out.get("llmError")
    assert out.get("cover")
    assert out.get("knowledge")
    assert out.get("quality_gate_pass") is False
    # Cached/template cards may honestly lack grounded citations
    assert any(isinstance(item, dict) for item in out["knowledge"])


@pytest.mark.asyncio
async def test_run_scan_uses_shallow_research_then_compose(monkeypatch):
    from cn_social_agent.cards import service as svc

    calls: dict[str, Any] = {}

    async def fake_research(*a, **k):
        calls["research"] = {"args": a, "kwargs": k}
        return {
            "ok": True,
            "evidencePack": {
                "evidences": [
                    {
                        "id": "e1",
                        "text": "招聘岗位要求 RAG 与向量检索重排经验三年任职",
                        "selected": True,
                        "score": 3,
                    }
                ],
                "count": 1,
            },
            "mode": "research",
            "persisted": "none",
        }

    async def fake_compose(*a, **k):
        calls["compose"] = {"args": a, "kwargs": k}
        return {
            "ok": True,
            "mode": "journal",
            "cover": {"title": "T", "edition": "第 1 期"},
            "knowledge": [{"topicTitle": "A", "evidenceIds": ["e1"]}],
            "evidencePack": k.get("evidence_pack") or {},
            "id": "h_compose",
        }

    monkeypatch.setattr(svc, "run_research", fake_research)
    monkeypatch.setattr(svc, "run_compose", fake_compose)
    out = await svc.run_scan(["R"], use_workbench_llm=False)
    assert calls["research"]["kwargs"].get("depth") == "shallow"
    assert calls["research"]["kwargs"].get("persist") is False
    assert calls["compose"]["kwargs"].get("persist") is True
    assert calls["compose"]["kwargs"].get("min_selected") == 0
    assert out["mode"] == "ai"
    assert out.get("cover")
    assert out.get("knowledge")


@pytest.mark.asyncio
async def test_research_compose_http(monkeypatch):
    """login → research → compose → history item has evidencePack."""
    from aiohttp.test_utils import TestClient, TestServer

    from cn_social_agent.api import create_app
    from cn_social_agent.cards import service as svc
    from cn_social_agent.cards.build import normalize_llm_payload

    monkeypatch.setenv("WORKBENCH_STORE", "memory")
    monkeypatch.setenv("WORKBENCH_LLM", "mock")

    role = "AI Agent 开发工程师"
    fake_rows = [
        [
            {
                "text": f"招聘{role}岗位职责含 LangGraph 编排与工具调用经验三年任职要求{i}",
                "query": f"q{i}",
                "engine": "bing",
                "role": role,
            }
            for i in range(6)
        ]
    ]
    monkeypatch.setattr(svc, "scan_roles", AsyncMock(return_value=fake_rows))

    async def fake_compose(roles, *, evidence_pack, **kwargs):
        eid = (evidence_pack.get("evidences") or [{}])[0].get("id") or "e1"
        return normalize_llm_payload(
            {
                "cover": {
                    "title": "HTTP刊",
                    "description": "读者将学会具名编排与检验标准的评估方法一二三四",
                    "tags": ["编排", "检索", "交付"],
                },
                "knowledge": [
                    {
                        "topicTitle": "编排",
                        "concept": "c" * 40,
                        "keyPoint": "- a\n- b\n- c",
                        "example": "e" * 30,
                        "evidenceIds": [eid],
                    },
                    {
                        "topicTitle": "检索",
                        "concept": "c" * 40,
                        "keyPoint": "- a\n- b\n- c",
                        "example": "e" * 30,
                        "evidenceIds": [eid],
                    },
                    {
                        "topicTitle": "交付",
                        "concept": "c" * 40,
                        "keyPoint": "- a\n- b\n- c",
                        "example": "e" * 30,
                        "evidenceIds": [eid],
                    },
                ],
            },
            roles if isinstance(roles, list) else [role],
            category="hiring_insight",
            evidence_pack=evidence_pack,
        )

    monkeypatch.setattr(svc, "compose_with_llm", fake_compose)

    app = create_app()
    async with TestClient(TestServer(app)) as client:
        login = await client.post(
            "/api/auth/login",
            json={"email": "demo@local.test", "password": "demo123456"},
        )
        assert login.status == 200
        token = (await login.json())["accessToken"]
        headers = {"Authorization": f"Bearer {token}"}

        research = await client.post(
            "/api/cards/research",
            json={"roles": [role], "category": "hiring_insight"},
            headers=headers,
        )
        assert research.status == 200
        research_body = await research.json()
        pack_id = research_body.get("packId") or research_body.get("id")
        assert pack_id
        assert research_body.get("evidencePack", {}).get("count", 0) >= 1

        compose = await client.post(
            "/api/cards/compose",
            json={"roles": [role], "packId": pack_id, "category": "hiring_insight"},
            headers=headers,
        )
        assert compose.status == 200
        compose_body = await compose.json()
        assert compose_body.get("cover")
        assert compose_body.get("knowledge")
        assert compose_body.get("evidencePack", {}).get("count", 0) >= 1
        item_id = compose_body.get("id")
        assert item_id

        hist = await client.get(
            f"/api/cards/history?id={item_id}",
            headers=headers,
        )
        assert hist.status == 200
        item = await hist.json()
        assert item.get("evidencePack", {}).get("count", 0) >= 1
        assert item.get("cover")
        assert item.get("knowledge")

