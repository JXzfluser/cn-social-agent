# 知识期刊 · 丰满成刊 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 成刊产出带导读页、目录页、5–6 张加长知识卡，并按 `diagram.type` 渲染六类图示，使期刊完整清晰。

**Architecture:** 在现有 `compose_with_llm` → `normalize_llm_payload` → workshop 预览链上扩展：normalize 产出 `frontMatter` + 每卡 `diagram`；LLM 大纲/扩写按新字数与 diagram 约束；`cards_workshop.js` 增加导读/目录画布与多图示渲染，导出页序与预览一致。快扫可不带 frontMatter（兼容）。

**Tech Stack:** 现有 Python cards 管道 + `cards_workshop.js` / `index.html`；无新框架。

**Spec:** [`docs/superpowers/specs/2026-08-13-journal-rich-compose-design.md`](../specs/2026-08-13-journal-rich-compose-design.md)

---

## File map

| File | Responsibility |
|------|----------------|
| `src/cn_social_agent/cards/diagram.py` | `infer_diagram_type`、`normalize_diagram`、合法 type 集合 |
| `src/cn_social_agent/cards/build.py` | normalize：字数、5–6 卡、frontMatter、挂 diagram |
| `src/cn_social_agent/cards/llm.py` | `compose_with_llm` 大纲/扩写提示词（promises、diagram、加长） |
| `src/cn_social_agent/cards/service.py` | `run_compose` 透传 `frontMatter` 入 history |
| `src/cn_social_agent/workbench/cards_workshop.js` | 导读/目录/六图示渲染、减弱 clamp、编辑、导出页序 |
| `tests/workbench/test_journal_rich_compose.py` | normalize / diagram / frontMatter / mock compose |

---

### Task 1: diagram 辅助 + normalize frontMatter

**Files:**
- Create: `src/cn_social_agent/cards/diagram.py`
- Modify: `src/cn_social_agent/cards/build.py`
- Create: `tests/workbench/test_journal_rich_compose.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/workbench/test_journal_rich_compose.py
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
```

- [ ] **Step 2: 跑测确认失败**

Run: `PYTHONPATH=src python3 -m pytest tests/workbench/test_journal_rich_compose.py::test_infer_diagram_type -v`  
Expected: ImportError

- [ ] **Step 3: 实现 `diagram.py`**

```python
DIAGRAM_TYPES = frozenset({"flow", "cycle", "compare", "stack", "callout", "bullets"})
KIND_DEFAULT = {
    "steps": "flow",
    "compare": "compare",
    "data": "callout",
    "quote": "callout",
    "keypoints": "bullets",
    "concept": "stack",
}

def infer_diagram_type(card_kind: str) -> str:
    return KIND_DEFAULT.get((card_kind or "").lower(), "bullets")

def normalize_diagram(raw, *, card_kind: str, flow=None, compare_left="", compare_right="", metric="", quote="") -> dict:
    d = raw if isinstance(raw, dict) else {}
    t = str(d.get("type") or "").lower()
    if t not in DIAGRAM_TYPES:
        t = infer_diagram_type(card_kind)
    nodes = []
    for n in (d.get("nodes") or [])[:5]:
        if isinstance(n, dict) and n.get("label"):
            nodes.append({"label": str(n["label"])[:10], "note": str(n.get("note") or "")[:24]})
        elif isinstance(n, str) and n.strip():
            nodes.append({"label": n.strip()[:10], "note": ""})
    if not nodes and flow:
        nodes = [{"label": str(s)[:10], "note": ""} for s in flow[:5] if str(s).strip()]
    if t == "compare" and len(nodes) < 2:
        nodes = [{"label": (compare_left or "误区")[:10], "note": ""},
                 {"label": (compare_right or "正解")[:10], "note": ""}]
    if t == "callout" and not nodes:
        label = (metric or quote or "要点")[:10]
        nodes = [{"label": label, "note": ""}]
    if len(nodes) < 2 and t in ("flow", "cycle", "stack", "bullets"):
        nodes = nodes + [{"label": f"步骤{i}", "note": ""} for i in range(len(nodes) + 1, 3)]
    return {"type": t, "nodes": nodes[:5]}
```

- [ ] **Step 4: 扩展 `normalize_llm_payload`**

增加参数 `rich_journal: bool = False`：

- `rich_journal=True`（compose 路径）：`knowledge_raw[:6]`，pad 到至少 **5**（不足用 theme 补且挂 diagram）；concept clip 放宽到 ~220；realPoints 最多 6  
- 每卡调用 `normalize_diagram`；写入 `card["diagram"]`  
- 解析/补全 `frontMatter.guide.promises`（恰好 3，clip 28）；`meta` 用证据数+roles  
- `toc` 由 knowledge 生成：`{index, title, kind, diagram}`  
- `rich_journal=False`（旧 generate / 快扫）：行为保持可 3 卡、可不写 frontMatter（或 frontMatter=null）

`_normalize_one_card`：保留更长 concept（若 rich）；不要把 150 字 concept 裁成过短。

- [ ] **Step 5: 跑通测试**

`PYTHONPATH=src python3 -m pytest tests/workbench/test_journal_rich_compose.py -q`  
Expected: PASS；并跑 `test_knowledge_journal.py` 回归。

- [ ] **Step 6: Commit**（无 git 则跳过）

---

### Task 2: compose_with_llm 丰满提示词

**Files:**
- Modify: `src/cn_social_agent/cards/llm.py`
- Modify: `src/cn_social_agent/cards/service.py`（compose 调 normalize 时 `rich_journal=True`）
- Test: `tests/workbench/test_journal_rich_compose.py`

- [ ] **Step 1: 测试 mock compose 产出 frontMatter**

```python
@pytest.mark.asyncio
async def test_compose_with_llm_rich_outline(monkeypatch):
    from cn_social_agent.cards import llm as llm_mod
    from cn_social_agent.cards.evidence import build_pack

    async def fake_complete_json(*, messages, **k):
        content = messages[-1]["content"]
        if "规划" in content or "大纲" in content:
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
```

- [ ] **Step 2: 改 `compose_with_llm`**

大纲 JSON 增加：

```text
"frontMatter":{"guide":{"headline":"本期导读","promises":["≤28字","≤28字","≤28字"]}},
每卡增加 "diagram":{"type":"flow|cycle|compare|stack|callout|bullets"}
目标 5–6 张；至少 3 种 card_kind；禁止清一色 flow
```

扩写：

```text
concept 140–220字；keyPoint 4–6条；example 90–140字
补全 diagram.nodes（label≤10）；steps→flow/cycle；compare 双侧；data metric；quote 金句
```

`normalize_llm_payload(..., rich_journal=True, evidence_pack=...)`。

- [ ] **Step 3: `run_compose` 保存 `frontMatter`**

history rec 增加 `frontMatter`；payload 返回带上。

- [ ] **Step 4: 跑测**

`PYTHONPATH=src python3 -m pytest tests/workbench/test_journal_rich_compose.py tests/workbench/test_knowledge_journal.py -q`

---

### Task 3: 预览渲染 — 导读 / 目录 / 六图示

**Files:**
- Modify: `src/cn_social_agent/workbench/cards_workshop.js`

- [ ] **Step 1: 图示函数**

在 `flowDiagram` 旁增加：

- `cycleDiagram(nodes)` — CSS 环形或 2×2+中心简图  
- `stackDiagram(nodes)` — 自下而上色条  
- `bulletsDiagram(nodes)` — 左侧编号轨  
- `calloutDiagram(nodes, {metric, quote})` — 大字  
- `compareDiagram` — 复用/抽离现有 compare 布局  
- `renderDiagram(diagram, fallbacks)` — switch type  

- [ ] **Step 2: `renderGuideHtml` / `renderTocHtml`**

1080×1440 画布：导读三承诺大号列表；目录为编号+title+kind 小标签。

- [ ] **Step 3: 预览栈与导出**

`renderPreview` / 导出 host：  
`cover → guide? → toc? → knowledge[]`  
仅当 `frontMatter.guide.promises?.length` 与 `toc?.length` 存在时插入。

- [ ] **Step 4: 减弱 clamp**

concept `-webkit-line-clamp` → 7–8；points 展示最多 6 条；example clamp → 5。

- [ ] **Step 5: `node --check` + 手动说明**

无浏览器自动化则自检语法；旧 payload 无 frontMatter 不插页。

---

### Task 4: 编辑器 + 导出页序收尾

**Files:**
- Modify: `cards_workshop.js`（及必要时 `index.html` 无新按钮）

- [ ] **Step 1: 编辑 frontMatter**

右侧：若有 guide，三 promethean 文本框；改则写回 `state.frontMatter` 并 `renderPreview`。

- [ ] **Step 2: 卡编辑 diagram**

`diagram.type` select（六类）；nodes 用多行 `label|note` 或简单三个 input。

- [ ] **Step 3: toc 与 knowledge 标题同步**

改 toc title → 对应 `knowledge[i].topicTitle`；或目录只读显示。

- [ ] **Step 4: applyPayload**

恢复 `frontMatter`；缺省 `{}` 不崩。

- [ ] **Step 5: 回归测试**

`PYTHONPATH=src python3 -m pytest tests/workbench/test_journal_rich_compose.py tests/workbench/test_knowledge_journal.py tests/workbench/test_knowledge_cards.py -q`

---

## Spec coverage

| Spec | Task |
|------|------|
| frontMatter guide/toc | 1–2 |
| 5–6 卡 + 加长字数 | 1–2 |
| diagram 六类 + 推断 | 1、3 |
| 预览页序 / 导出 | 3–4 |
| 编辑器 | 4 |
| 快扫无 frontMatter 兼容 | 1（rich_journal=False）、3 |
| 测试 | 1–2、4 |

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-13-journal-rich-compose.md`.

**两种执行方式：**

1. **Subagent-Driven（推荐）** — 每任务新开子代理，任务间复核  
2. **Inline Execution** — 本会话连续推进  

你要哪一种？
