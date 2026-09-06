"""Tests for journal depth report + flow/evidence quality fixes."""

from __future__ import annotations

import json
from pathlib import Path

from cn_social_agent.cards.build import normalize_flow, normalize_llm_payload, short_step
from cn_social_agent.cards.evidence import (
    build_pack,
    clean_snippet_text,
    looks_like_serp_noise,
    validate_evidence_ids,
)
from cn_social_agent.cards.quality import journal_depth_report


def test_short_step_cjk_no_dangling_connector():
    s = short_step("解决开发者在重复性编码任务中的效率瓶颈", 16)
    assert not s.endswith("的")
    assert "效" not in s or s.endswith("效率") or len(s) < 16


def test_short_step_strips_short_dangling_connector():
    # Regression: 6-char items ending in a CJK connector (整体流程中的) took the
    # early return `len(head) <= n` unchanged, then failed the flow gate.
    for broken in ("整体流程中的", "通过中间件与", "部署到环境中的"):
        fixed = short_step(broken)
        assert not fixed.endswith(("的", "中", "与", "到"))
        assert fixed != broken


def test_normalize_flow_heals_short_dangling_without_point_match():
    # Regression: _flow_item_looks_cut only flagged dangling connectors at len>=8,
    # while the gate flags at len>=6 — 6-7 char cuts were kept and failed the gate.
    pts = ["关键步骤一", "关键步骤二"]
    broken = ["整体流程中的", "通过中间件与"]
    fixed = normalize_flow(broken, pts)
    assert fixed
    assert not any(str(f).endswith(("的", "中", "与")) for f in fixed)
    assert report_flow_clean(fixed)


def report_flow_clean(flow: list[str]) -> bool:
    payload = {
        "cover": {"title": "T", "description": "D", "marketNote": "M"},
        "frontMatter": {"guide": {"promises": ["a", "b", "c"]}, "toc": [{"index": 1}]},
        "knowledge": [
            {"topicTitle": "t1", "card_kind": "concept", "realPoints": ["p1", "p2"], "flow": flow}
        ],
    }
    return journal_depth_report(payload).get("checks", {}).get("flow_not_truncated", False)


def test_normalize_flow_heals_mid_phrase_cuts():
    pts = [
        "解决开发者在重复性编码任务中的效率瓶颈",
        "通过自然语言指令驱动代码生成与执行",
    ]
    broken = [
        "解决开发者在重复性编码任务中的效",
        "通过自然语言指令驱动代码生成与执",
    ]
    fixed = normalize_flow(broken, pts)
    assert fixed
    assert not any(x.endswith(("的", "效", "执")) for x in fixed)


def test_clean_snippet_strips_serp_chrome():
    raw = (
        'xAI 发布 Grok Build :重新定义开发工具的 Agentic CLI OSCHINA...'
        '"}],"clamp":2}],"isSingleLine":false},"isPc":true,"summarySpan":12'
    )
    cleaned = clean_snippet_text(raw)
    assert "clamp" not in cleaned.lower()
    assert "isPc" not in cleaned
    assert looks_like_serp_noise(raw) is True
    assert looks_like_serp_noise("Grok Build 开源 9 天 Star 破 2 万，开发者关注度高") is False


def test_build_pack_drops_serp_noise():
    pack = build_pack(
        [
            {
                "text": '垃圾 {"clamp":2,"isPc":true,"summarySpan":12} 样式碎片',
                "role": "xai-org/grok-build",
                "query": "q",
                "engine": "bing",
            },
            {
                "text": "Grok Build 产品功能亮点：全屏 TUI、工作流编译器与上手教程，适合开发者实战落地。",
                "role": "xai-org/grok-build",
                "query": "q",
                "engine": "bing",
            },
        ],
        category="product_explain",
    )
    texts = " ".join(e["text"] for e in pack["evidences"])
    assert "clamp" not in texts.lower()
    assert pack["count"] >= 1


def test_validate_evidence_ids_requires_token_overlap():
    pack = build_pack(
        [
            {
                "text": "招聘岗位职责含 LangGraph 状态机与工具调用三年经验",
                "role": "R",
                "query": "q",
                "engine": "bing",
            }
        ]
    )
    eid = pack["evidences"][0]["id"]
    # Unrelated card text → no silent top-score attach
    assert validate_evidence_ids(["nope"], pack, card_text="蔬菜沙拉营养搭配") == []
    # Overlapping tokens → backfill
    ids = validate_evidence_ids(["nope"], pack, card_text="LangGraph 工具调用")
    assert ids == [eid]


def test_journal_depth_report_flags_grok_sample_gaps():
    path = Path("data/cards/e_demo_at_local.test.json")
    if not path.is_file():
        return
    rows = json.loads(path.read_text(encoding="utf-8"))
    doc = next(
        (
            r
            for r in rows
            if isinstance(r, dict)
            and (r.get("cover") or {}).get("edition") == "第 2 期"
            and "Grok Build" in str((r.get("cover") or {}).get("title") or "")
        ),
        rows[0] if rows else None,
    )
    assert doc
    report = journal_depth_report(doc, rich_journal=True)
    # Sample is known-thin: truncated tags, SERP marketNote, and/or cut flow labels
    assert report["ok"] is False
    assert set(report["failed"]) & {
        "has_front_matter",
        "flow_not_truncated",
        "cover_tags_ok",
        "market_note_clean",
    }


def test_normalize_heals_flow_and_tags():
    out = normalize_llm_payload(
        {
            "cover": {
                "title": "Grok Build 产品科普",
                "tags": ["Agentic C…", "xAI"],
                "marketNote": '实战:让AI接管…"}],"clamp":2,"isPc":true',
                "description": "了解定位与安全风险，评估是否接入。",
            },
            "frontMatter": {
                "guide": {
                    "headline": "本期导读",
                    "promises": ["看清定位", "跑通启动", "避开上传风险"],
                    "meta": "基于证据",
                },
                "toc": [],
            },
            "knowledge": [
                {
                    "topicTitle": "定位是 Agentic CLI",
                    "card_kind": "concept",
                    "concept": "Grok Build 是面向开发者的终端编程代理，用自然语言驱动编码与调试。" * 2,
                    "keyPoint": "- 终端代理\n- 自然语言驱动\n- 全屏 TUI\n- 多模型",
                    "example": "输入重构 auth 模块，自动改代码并给出可运行结果。",
                    "flow": ["解决开发者在重复性编码任务中的效", "通过自然语言指令驱动代码生成与执"],
                    "realPoints": [
                        "解决开发者在重复性编码任务中的效率瓶颈",
                        "通过自然语言指令驱动代码生成与执行",
                    ],
                    "evidenceIds": ["e1"],
                },
                {
                    "topicTitle": "工作流编译器对比",
                    "card_kind": "compare",
                    "concept": "用可组合节点替代反复调 prompt，结果更可复用。" * 2,
                    "keyPoint": "- 提示词不稳\n- 节点可复用\n- 工具编排\n- 降低门槛",
                    "example": "定义读取→测试→报告节点，一次跑通结构化结果。",
                    "compare_left": "反复调试 prompt",
                    "compare_right": "工作流节点编排",
                    "evidenceIds": ["e1"],
                },
                {
                    "topicTitle": "启动授权三步",
                    "card_kind": "steps",
                    "concept": "安装后启动，浏览器完成 xAI 授权即可进入 TUI。" * 2,
                    "keyPoint": "- 安装启动\n- 浏览器授权\n- 进入 TUI\n- 无需手填 Key",
                    "example": "执行启动命令，授权成功后进入交互界面。",
                    "flow": ["启动", "授权", "进入 TUI"],
                    "evidenceIds": ["e1"],
                },
                {
                    "topicTitle": "9 天 2 万 Star",
                    "card_kind": "data",
                    "concept": "开源初期社区热度验证了开发者对终端 Agent 的需求。" * 2,
                    "keyPoint": "- 9 天破 2 万\n- 社区传播快\n- 需求强烈\n- 现象级项目",
                    "example": "同期同类工具增速明显更低，形成传播差。",
                    "metric": "20000+",
                    "metric_note": "9 天 Star",
                    "evidenceIds": ["e1"],
                },
                {
                    "topicTitle": ".env 明文上传风险",
                    "card_kind": "keypoints",
                    "concept": "抓包显示仓库与 .env 可能被无条件上传，敏感信息有泄露风险。" * 2,
                    "keyPoint": "- .env 明文\n- 全仓上传\n- 无法关闭\n- 评估后再用",
                    "example": "含 SECRET_KEY 的仓库接入前应先隔离敏感文件。",
                    "evidenceIds": ["e1"],
                },
            ],
        },
        ["xai-org/grok-build"],
        category="product_explain",
        rich_journal=True,
        evidence_pack=build_pack(
            [
                {
                    "text": "Grok Build 产品功能与工作流编译器、TUI 上手教程，以及 .env 上传安全风险讨论。",
                    "role": "xai-org/grok-build",
                    "query": "q",
                    "engine": "bing",
                }
            ],
            category="product_explain",
        ),
    )
    for k in out["knowledge"]:
        for f in k.get("flow") or []:
            assert not str(f).endswith(("的", "效", "执", "授"))
    assert all(not str(t).endswith("…") for t in out["cover"].get("tags") or [])
    assert "clamp" not in str(out["cover"].get("marketNote") or "").lower()
    report = journal_depth_report(out, rich_journal=True)
    assert report["checks"]["flow_not_truncated"] is True
    assert report["checks"]["cards_ge_5"] is True
    assert report["checks"]["kinds_ge_3"] is True
