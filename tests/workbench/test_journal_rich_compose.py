import pytest

from cn_social_agent.cards.build import normalize_llm_payload
from cn_social_agent.cards.diagram import infer_diagram_type, normalize_diagram


def test_infer_diagram_type():
    assert infer_diagram_type("steps") == "flow"
    assert infer_diagram_type("compare") == "compare"
    assert infer_diagram_type("data") == "callout"
    assert infer_diagram_type("keypoints") == "bullets"
    assert normalize_diagram({"type": "nope"}, card_kind="steps")["type"] == "flow"


def test_normalize_rich_front_matter_and_diagram():
    pack = {"evidences": [
        {"id": "e1", "text": "招聘要求 LangGraph 编排与工具调用三年经验岗位职责", "score": 3, "selected": True}
    ]}
    parsed = {
        "cover": {"title": "丰满刊", "description": "读者将学会编排、检索与交付检验的完整评估方法一二"},
        "frontMatter": {"guide": {"headline": "本期导读", "promises": ["能画状态机", "能量化召回", "能量本交付"]}},
        "knowledge": [
            {"topicTitle": "编排闭环", "card_kind": "steps", "concept": "c" * 150,
             "keyPoint": "- a\n- b\n- c\n- d", "example": "e" * 100,
             "diagram": {"type": "cycle", "nodes": [{"label": "规划"}, {"label": "工具"}, {"label": "回退"}]},
             "evidenceIds": ["e1"]},
            {"topicTitle": "检索工程", "card_kind": "keypoints", "concept": "c" * 150,
             "keyPoint": "- a\n- b\n- c\n- d", "example": "e" * 100, "evidenceIds": ["e1"]},
            {"topicTitle": "误区对照", "card_kind": "compare", "concept": "c" * 150,
             "keyPoint": "- a\n- b\n- c\n- d", "example": "e" * 100,
             "compare": {"left": "只调API", "right": "状态机"}, "evidenceIds": ["e1"]},
            {"topicTitle": "交付指标", "card_kind": "data", "concept": "c" * 150,
             "keyPoint": "- a\n- b\n- c\n- d", "example": "e" * 100,
             "metric": "p95", "metric_note": "延迟", "evidenceIds": ["e1"]},
            {"topicTitle": "金句", "card_kind": "quote", "concept": "c" * 80,
             "quote": "编排不是多聊几轮", "keyPoint": "- a\n- b\n- c\n- d",
             "example": "e" * 100, "evidenceIds": ["e1"]},
        ],
    }
    out = normalize_llm_payload(
        parsed, ["AI Agent"], category="hiring_insight", evidence_pack=pack, rich_journal=True
    )
    assert 5 <= len(out["knowledge"]) <= 6
    fm = out["frontMatter"]
    assert len(fm["guide"]["promises"]) == 3
    assert len(fm["toc"]) == len(out["knowledge"])
    assert out["knowledge"][0]["diagram"]["type"] == "cycle"
    assert out["knowledge"][1]["diagram"]["type"] in ("bullets", "flow", "stack", "callout", "compare", "cycle")


@pytest.mark.asyncio
async def test_compose_with_llm_rich_outline(monkeypatch):
    from cn_social_agent.cards import llm as llm_mod
    from cn_social_agent.cards.evidence import build_pack

    async def fake_complete_json(*, messages, **k):
        content = messages[-1]["content"]
        if ("规划" in content or "大纲" in content) and "扩写" not in content:
            return {
                "cover": {"title": "能力刊", "description": "d" * 60, "tags": ["a", "b", "c"]},
                "frontMatter": {"guide": {"promises": ["P1能验证编排", "P2能量化检索", "P3能量本交付"]}},
                "knowledge": [
                    {"topicTitle": f"T{i}", "card_kind": k, "diagram": {"type": d}, "evidenceIds": ["e1"]}
                    for i, (k, d) in enumerate([
                        ("steps", "cycle"), ("keypoints", "bullets"), ("compare", "compare"),
                        ("data", "callout"), ("quote", "callout"),
                    ], 1)
                ],
            }
        return {
            "knowledge": [
                {
                    "topicTitle": f"T{i}", "card_kind": "steps", "concept": "概念" * 40,
                    "keyPoint": "- 一\n- 二\n- 三\n- 四", "example": "例子" * 25,
                    "diagram": {"type": "flow", "nodes": [{"label": "a"}, {"label": "b"}, {"label": "c"}]},
                    "evidenceIds": ["e1"], "flow": ["a", "b", "c"],
                }
                for i in range(1, 6)
            ]
        }

    monkeypatch.setattr(llm_mod, "_complete_json", fake_complete_json)
    pack = build_pack([{"text": "招聘岗位要求 LangGraph 与工具调用经验三年", "role": "R", "query": "q", "engine": "bing"}])
    out = await llm_mod.compose_with_llm(["R"], evidence_pack=pack, workbench_llm=object())
    assert len(out["frontMatter"]["guide"]["promises"]) == 3
    assert 5 <= len(out["knowledge"]) <= 6
    assert all(k.get("diagram") for k in out["knowledge"])


@pytest.mark.asyncio
async def test_run_compose_persists_front_matter(monkeypatch):
    from cn_social_agent.cards import service as svc
    from cn_social_agent.cards.build import normalize_llm_payload
    from cn_social_agent.cards.evidence import build_pack

    pack = build_pack(
        [
            {
                "text": "招聘岗位要求 LangGraph 与工具调用经验三年岗位职责",
                "role": "R",
                "query": "q",
                "engine": "bing",
            }
        ]
    )
    eid = pack["evidences"][0]["id"]

    async def fake_compose(*a, **k):
        return normalize_llm_payload(
            {
                "cover": {"title": "丰满刊", "description": "d" * 60},
                "frontMatter": {
                    "guide": {"headline": "本期导读", "promises": ["能画状态机", "能量化召回", "能量本交付"]}
                },
                "knowledge": [
                    {
                        "topicTitle": f"T{i}",
                        "card_kind": kind,
                        "concept": "c" * 150,
                        "keyPoint": "- a\n- b\n- c\n- d",
                        "example": "e" * 100,
                        "diagram": {"type": dtype, "nodes": [{"label": "a"}, {"label": "b"}, {"label": "c"}]},
                        "evidenceIds": [eid],
                    }
                    for i, (kind, dtype) in enumerate(
                        [
                            ("steps", "cycle"),
                            ("keypoints", "bullets"),
                            ("compare", "compare"),
                            ("data", "callout"),
                            ("quote", "callout"),
                        ],
                        1,
                    )
                ],
            },
            ["R"],
            evidence_pack=pack,
            rich_journal=True,
        )

    saved = {}

    def fake_save(rec, **kw):
        saved["rec"] = rec
        return {**rec, "id": "hist-fm-1"}

    monkeypatch.setattr(svc, "compose_with_llm", fake_compose)
    monkeypatch.setattr(svc, "save_history_record", fake_save)
    out = await svc.run_compose(
        roles_raw=["R"], evidence_pack=pack, use_workbench_llm=False, persist=True
    )
    assert len(out["frontMatter"]["guide"]["promises"]) == 3
    assert "frontMatter" in saved["rec"]
    assert len(saved["rec"]["frontMatter"]["guide"]["promises"]) == 3
