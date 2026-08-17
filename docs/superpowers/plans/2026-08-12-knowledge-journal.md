# 知识期刊 · 采编 → 成刊 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将知识卡片升级为「深采 Evidence Pack → 灵活成刊」两段式知识期刊，快扫路径兼容旧 `/api/cards/scan`。

**Architecture:** 新建 `evidence.py` 负责证据条目/打分/打包；加深 `scrape.py` 按 depth 控 query 与早停；`service.py` 拆出 `run_research` / `run_compose`，`run_scan` 变为浅 research+compose；`llm.py` 增加基于证据的大纲+扩写；工坊 UI 主路径改为深采/成刊+素材台账。

**Tech Stack:** Python 3 + aiohttp + httpx + 现有 workbench LLM；前端 `cards_workshop.js` / `index.html`；本地 `data/cards/*.json` + 可选 InsForge。

**Spec:** [`docs/superpowers/specs/2026-08-12-knowledge-journal-design.md`](../specs/2026-08-12-knowledge-journal-design.md)

---

## File map

| File | Responsibility |
|------|----------------|
| `src/cn_social_agent/cards/evidence.py` | Evidence 条目、打分、去重、merge pack、选中过滤、非法 ID 回填 |
| `src/cn_social_agent/cards/scrape.py` | `depth=shallow\|deep` 扫描；深采 6–8 query / 早停 18·30 |
| `src/cn_social_agent/cards/categories.py` | 每类补齐 6–8 条 `scrape_suffixes`；`llm_teach` 改为建议非硬约束 |
| `src/cn_social_agent/cards/llm.py` | `compose_with_llm(...)`：证据大纲→扩写；放宽 3–6 卡 |
| `src/cn_social_agent/cards/build.py` | `normalize_llm_payload` 支持 3–6 卡、`evidenceIds`、`stance` |
| `src/cn_social_agent/cards/service.py` | `run_research` / `run_compose` / 兼容 `run_scan` |
| `src/cn_social_agent/cards/history.py` | 保存/回载 `evidencePack`；`mode` 含 research/journal |
| `src/cn_social_agent/cards/cloud.py` | upsert 时尽量带上 `evidence_pack`（缺列则吞错） |
| `src/cn_social_agent/api/card_routes.py` | `POST research` / `POST compose`；scan 保留 |
| `src/cn_social_agent/workbench/index.html` | 深采/成刊/快扫按钮 + 素材台账 DOM |
| `src/cn_social_agent/workbench/cards_workshop.js` | research/compose 流程、台账勾选、证据芯片 |
| `tests/workbench/test_knowledge_journal.py` | 证据/normalize/research·compose 单元与 API |

---

### Task 1: Evidence 模型（打分 / 去重 / pack）

**Files:**
- Create: `src/cn_social_agent/cards/evidence.py`
- Create: `tests/workbench/test_knowledge_journal.py`
- Modify: `src/cn_social_agent/cards/scrape.py`（导出 `score_snippet` 可调用的信号，或把打分迁到 evidence 并复用 `_SIGNAL_RE`）

- [ ] **Step 1: 写失败测试**

```python
# tests/workbench/test_knowledge_journal.py
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

def test_merge_and_filter_selected():
    a = build_pack([{"text": "招聘岗位职责含 RAG 向量检索与重排经验要求", "role": "R", "query": "q", "engine": "bing"}])
    b = build_pack([{"text": "面试考察 LangGraph 状态机与失败回退交付物", "role": "R", "query": "q2", "engine": "bing"}])
    m = merge_packs(a, b)
    assert len(m["evidences"]) >= 2
    m["evidences"][0]["selected"] = False
    sel = selected_evidences(m)
    assert all(e.get("selected", True) for e in sel)

def test_validate_evidence_ids_drops_fake_and_backfills():
    pack = build_pack([{"text": "招聘 JD 要求 Agent 工具调用与编排能力三年经验", "role": "A", "query": "q", "engine": "bing"}])
    eid = pack["evidences"][0]["id"]
    ids = validate_evidence_ids(["nope", eid], pack, card_text="工具调用 编排")
    assert eid in ids
    assert "nope" not in ids
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONPATH=src python3 -m pytest tests/workbench/test_knowledge_journal.py::test_build_pack_assigns_ids_and_sorts -v`  
Expected: `ImportError` 或 `ModuleNotFoundError`

- [ ] **Step 3: 实现 `evidence.py`**

```python
# src/cn_social_agent/cards/evidence.py
"""Evidence pack: score, dedupe, merge, citation validation."""
from __future__ import annotations
import re
from typing import Any
from cn_social_agent.cards.scrape import is_useful_snippet, _SIGNAL_RE  # or duplicate thin helpers

def score_snippet(text: str, *, role: str = "") -> tuple[float, list[str]]:
    t = (text or "").strip()
    if not is_useful_snippet(t, role=role):
        return 0.0, []
    signals = list(dict.fromkeys(_SIGNAL_RE.findall(t)))
    score = float(len(signals))
    if role and role in t:
        score += 2.0
    score += min(len(t) / 200.0, 1.5)
    return score, signals[:8]

def build_pack(raw_items: list[dict[str, Any]], *, limit: int = 40) -> dict[str, Any]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for item in raw_items:
        text = re.sub(r"\s+", " ", str(item.get("text") or "")).strip()[:400]
        role = str(item.get("role") or "")
        sc, signals = score_snippet(text, role=role)
        if sc <= 0 or text in seen:
            continue
        seen.add(text)
        rows.append({
            "text": text,
            "query": str(item.get("query") or "")[:120],
            "engine": str(item.get("engine") or "")[:16],
            "role": role[:40],
            "score": round(sc, 2),
            "signals": signals,
            "url": str(item.get("url") or "")[:200],
            "title": str(item.get("title") or "")[:80],
            "selected": True,
        })
    rows.sort(key=lambda e: e["score"], reverse=True)
    rows = rows[:limit]
    for i, e in enumerate(rows, 1):
        e["id"] = f"e{i}"
    return {"evidences": rows, "count": len(rows)}

def merge_packs(a: dict[str, Any] | None, b: dict[str, Any] | None, *, limit: int = 40) -> dict[str, Any]:
    raw = []
    for pack in (a, b):
        for e in (pack or {}).get("evidences") or []:
            raw.append(e)
    # rebuild to re-id; preserve selected=False by text key if needed
    selected_map = {e["text"]: e.get("selected", True) for e in raw if e.get("text")}
    pack = build_pack(raw, limit=limit)
    for e in pack["evidences"]:
        e["selected"] = selected_map.get(e["text"], True)
    return pack

def selected_evidences(pack: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [e for e in (pack or {}).get("evidences") or [] if e.get("selected", True)]

def validate_evidence_ids(
    ids: list[str] | None,
    pack: dict[str, Any] | None,
    *,
    card_text: str = "",
    min_count: int = 1,
) -> list[str]:
    by_id = {e["id"]: e for e in (pack or {}).get("evidences") or []}
    out = [i for i in (ids or []) if i in by_id]
    if len(out) >= min_count:
        return out[:4]
    # backfill: highest score whose text overlaps card tokens
    tokens = [t for t in re.split(r"\W+", card_text) if len(t) >= 2][:12]
    ranked = sorted((pack or {}).get("evidences") or [], key=lambda e: e.get("score", 0), reverse=True)
    for e in ranked:
        if e["id"] in out:
            continue
        if not tokens or any(t in e["text"] for t in tokens):
            out.append(e["id"])
        if len(out) >= min_count:
            break
    if not out and ranked:
        out = [ranked[0]["id"]]
    return out[:4]
```

若不想从 `scrape` 导出私有 `_SIGNAL_RE`，把信号正则挪到 `evidence.py`，`scrape.is_useful_snippet` 改为调用共享常量。

- [ ] **Step 4: 跑通测试**

Run: `PYTHONPATH=src python3 -m pytest tests/workbench/test_knowledge_journal.py -v`  
Expected: 上述 3 个测试 PASS

- [ ] **Step 5: Commit**（若仓库无 git 则跳过）

```bash
git add src/cn_social_agent/cards/evidence.py tests/workbench/test_knowledge_journal.py src/cn_social_agent/cards/scrape.py
git commit -m "feat(cards): evidence pack scoring and citation helpers"
```

---

### Task 2: 深采 / 浅采 scrape

**Files:**
- Modify: `src/cn_social_agent/cards/scrape.py`
- Modify: `src/cn_social_agent/cards/categories.py`（每类 `scrape_suffixes` 扩到 6–8 条）
- Test: `tests/workbench/test_knowledge_journal.py`

- [ ] **Step 1: 写失败测试（query 构建，不打外网）**

```python
def test_build_queries_deep_vs_shallow():
    from cn_social_agent.cards.scrape import build_queries
    shallow = build_queries("AI Agent 开发工程师", category="hiring_insight", depth="shallow")
    deep = build_queries("AI Agent 开发工程师", category="hiring_insight", depth="deep")
    assert 1 <= len(shallow) <= 3
    assert 6 <= len(deep) <= 8
    assert all('"' in q for q in deep)  # quoted role
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONPATH=src python3 -m pytest tests/workbench/test_knowledge_journal.py::test_build_queries_deep_vs_shallow -v`  
Expected: FAIL `build_queries` missing

- [ ] **Step 3: 实现 depth 参数**

在 `scrape.py` 增加：

```python
def build_queries(role: str, *, category: str = "hiring_insight", depth: str = "shallow") -> list[str]:
    from cn_social_agent.cards.categories import get_category
    cat = get_category(category)
    suffixes = list(cat.get("scrape_suffixes") or [])
    n = 3 if depth == "shallow" else 8
    return [_role_query(role, suf) for suf in suffixes[:n]]

async def scan_role(role: str, *, category: str = "hiring_insight", depth: str = "shallow") -> list[dict]:
    """Return list of raw evidence dicts {text,query,engine,role} (not yet packed)."""
    queries = build_queries(role, category=category, depth=depth)
    per_role_stop = 6 if depth == "shallow" else 18
    # ... existing fetch loops, but:
    # - track engine name
    # - append {"text", "query", "engine", "role"}
    # - early-stop when filter_snippets count >= per_role_stop
    # - do NOT return only strings; return structured rows
```

同步改 `scan_roles(..., depth=)`。保留薄包装：若调用方仍要 `list[str]`，在 service 浅路径用 `[r["text"] for r in rows]`。

`categories.py` 为四个分类各补满 6–8 条 suffixes（招聘含 JD/面试/LangGraph/RAG 等；产品/路线/行业同理）。

- [ ] **Step 4: 跑测试**

Run: `PYTHONPATH=src python3 -m pytest tests/workbench/test_knowledge_journal.py::test_build_queries_deep_vs_shallow tests/workbench/test_knowledge_cards.py::test_snippet_quality_filters_dictionary_noise -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(cards): deep vs shallow scrape query depth"
```

---

### Task 3: `run_research` + API

**Files:**
- Modify: `src/cn_social_agent/cards/service.py`
- Modify: `src/cn_social_agent/cards/history.py`（`save_history_record` 保留 `evidencePack`）
- Modify: `src/cn_social_agent/api/card_routes.py`
- Test: `tests/workbench/test_knowledge_journal.py`

- [ ] **Step 1: 写失败测试（mock scrape）**

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_run_research_builds_pack(monkeypatch):
    from cn_social_agent.cards import service as svc
    fake_rows = [[
        {"text": "招聘 AI Agent 岗位职责含 LangGraph 与工具调用三年经验", "query": "q", "engine": "bing", "role": "AI Agent 开发工程师"},
    ]]
    monkeypatch.setattr(svc, "scan_roles", AsyncMock(return_value=fake_rows))
    out = await svc.run_research(["AI Agent 开发工程师"], category="hiring_insight", depth="deep")
    assert out["mode"] == "research"
    assert out["evidencePack"]["count"] >= 1
    assert out["packId"] or out.get("id")
```

- [ ] **Step 2: 运行确认失败**

Expected: `AttributeError: run_research`

- [ ] **Step 3: 实现**

```python
# service.py
async def run_research(roles_raw, *, category="hiring_insight", depth="deep",
                       append_pack=None, user_id=None, email=None, edition=None):
    cat = get_category(category)
    roles = parse_roles(roles_raw, category=cat["id"])[:3]
    rows = await scan_roles(roles, category=cat["id"], depth=depth)
    flat = [item for role_rows in rows for item in role_rows]
    # If scan_roles still returns list[str], adapt: wrap into dicts
    pack = build_pack(flat, limit=40 if depth == "deep" else 12)
    if append_pack:
        pack = merge_packs(append_pack, pack, limit=40 if depth == "deep" else 12)
    if pack["count"] == 0:
        payload = {"ok": False, "error": "未采到可用证据（已过滤词典/导航噪声）",
                   "evidencePack": pack, "roles": roles, "category": cat["id"], "mode": "research"}
    else:
        payload = {"ok": True, "evidencePack": pack, "roles": roles, "category": cat["id"],
                   "mode": "research", "snippetCount": pack["count"],
                   "sources": [e["text"] for e in pack["evidences"][:6]]}
    # save history draft with evidencePack; set packId = record id
    rec = {**payload, "cover": {"title": cat["default_title"], "edition": format_edition(edition, user_id=user_id, email=email)},
           "knowledge": [], "edition": format_edition(edition, user_id=user_id, email=email)}
    saved = save_history_record(rec, user_id=user_id, email=email)
    payload["id"] = saved["id"]
    payload["packId"] = saved["id"]
    # cloud upsert best-effort
    return payload
```

`history.save_history_record`：把 `evidencePack` 原样写入 row。

`card_routes.py`：

```python
@require_user
async def research(request):
    body = await request.json() if request.can_read_body else {}
    ...
    append = None
    if body.get("appendPackId"):
        append = (get_history_item(...) or {}).get("evidencePack")
    payload = await run_research(..., depth="deep", append_pack=append, ...)
    return web.json_response(payload, status=200 if payload.get("ok", True) or payload.get("evidencePack") else 200)
```

`setup_card_routes`: `app.router.add_post("/api/cards/research", research)`

- [ ] **Step 4: 跑测试**

Run: `PYTHONPATH=src python3 -m pytest tests/workbench/test_knowledge_journal.py::test_run_research_builds_pack -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(cards): research API and evidence pack persistence"
```

---

### Task 4: `compose_with_llm` + normalize（灵活 3–6 卡 + evidenceIds）

**Files:**
- Modify: `src/cn_social_agent/cards/llm.py`
- Modify: `src/cn_social_agent/cards/build.py`
- Modify: `src/cn_social_agent/cards/categories.py`（`llm_teach` 改为建议）
- Test: `tests/workbench/test_knowledge_journal.py`

- [ ] **Step 1: 写 normalize 测试**

```python
def test_normalize_allows_4_to_6_cards_and_evidence_ids():
    from cn_social_agent.cards.build import normalize_llm_payload
    pack = {"evidences": [{"id": "e1", "text": "招聘要求 LangGraph", "score": 3, "selected": True}]}
    parsed = {
        "cover": {"title": "测试刊", "description": "读者将学会具名编排与检验标准的评估方法一二三四"},
        "knowledge": [
            {"topicTitle": "编排", "card_kind": "steps", "concept": "x" * 40,
             "keyPoint": "- a\n- b\n- c", "example": "y" * 30, "flow": ["a", "b", "c"],
             "evidenceIds": ["e1", "fake"]},
            {"topicTitle": "检索", "card_kind": "keypoints", "concept": "x" * 40,
             "keyPoint": "- a\n- b", "example": "y" * 30, "evidenceIds": ["e1"]},
            {"topicTitle": "交付", "card_kind": "data", "concept": "x" * 40,
             "keyPoint": "- a", "example": "y" * 30, "metric": "p95", "evidenceIds": []},
            {"topicTitle": "对比", "card_kind": "compare", "concept": "x" * 40,
             "keyPoint": "- a", "example": "y" * 30, "compare": {"left": "只调API", "right": "状态机"},
             "evidenceIds": ["e1"]},
        ],
    }
    out = normalize_llm_payload(parsed, ["AI Agent"], category="hiring_insight", evidence_pack=pack)
    assert 3 <= len(out["knowledge"]) <= 6
    for k in out["knowledge"]:
        assert k.get("evidenceIds")
        assert "fake" not in k["evidenceIds"]
```

- [ ] **Step 2: 运行确认失败**

Expected: `normalize_llm_payload` unexpected kwarg or pad-to-3 only

- [ ] **Step 3: 改 normalize**

- `knowledge_raw[:6]`，`while len < 3` 再 pad；**不要**强制截成 3  
- 每卡调用 `validate_evidence_ids`；无 ID → `stance: "opinion"`，有 → `"evidence"`  
- `marketNote`：若 cover 空，用 `pick_market_note([e["text"] for e in selected])`  
- 取消「concept 过短就整卡换成 THEMES」的激进替换（可仅补短字段，避免抹掉证据卡）

- [ ] **Step 4: 实现 `compose_with_llm`**

```python
async def compose_with_llm(roles, *, evidence_pack, ai=None, workbench_llm=None,
                           workbench_model="", category="hiring_insight",
                           edition=None, user_id=None, email=None):
    evid = selected_evidences(evidence_pack)
    ctx = "\n".join(f'{e["id"]} (score={e["score"]}): {e["text"][:120]}' for e in evid[:28])
    # Phase1 outline: cover + 3-6 topics each with evidenceIds from the list above
    # Phase2 expand: flexible fields by card_kind; NO mandatory 机制/易错/检验
    # anti_hollow + "禁止编造 evidenceIds；只能用列表中的 id"
    ...
    return normalize_llm_payload(parsed, roles, category=..., evidence_pack=evidence_pack, ...)
```

更新 `hiring_insight.llm_teach`：机制/易错/检验改为「可选建议」，keypoints 允许普通条目。

- [ ] **Step 5: 跑测试**

Run: `PYTHONPATH=src python3 -m pytest tests/workbench/test_knowledge_journal.py::test_normalize_allows_4_to_6_cards_and_evidence_ids -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git commit -am "feat(cards): evidence-aware compose and flexible card normalize"
```

---

### Task 5: `run_compose` + 兼容 `run_scan`

**Files:**
- Modify: `src/cn_social_agent/cards/service.py`
- Modify: `src/cn_social_agent/api/card_routes.py`
- Test: `tests/workbench/test_knowledge_journal.py` + 回归 `test_knowledge_cards.py`

- [ ] **Step 1: 写测试**

```python
@pytest.mark.asyncio
async def test_run_compose_attaches_pack(monkeypatch):
    from cn_social_agent.cards import service as svc
    from cn_social_agent.cards.evidence import build_pack
    pack = build_pack([{"text": "招聘岗位要求 RAG 与向量检索重排经验", "role": "R", "query": "q", "engine": "bing"}])
    async def fake_compose(*a, **k):
        return normalize_llm_payload(
            {"cover": {"title": "T", "description": "d" * 40},
             "knowledge": [
                 {"topicTitle": "A", "concept": "c" * 40, "keyPoint": "- a\n- b\n- c",
                  "example": "e" * 30, "evidenceIds": [pack["evidences"][0]["id"]]},
                 {"topicTitle": "B", "concept": "c" * 40, "keyPoint": "- a\n- b\n- c",
                  "example": "e" * 30, "evidenceIds": [pack["evidences"][0]["id"]]},
                 {"topicTitle": "C", "concept": "c" * 40, "keyPoint": "- a\n- b\n- c",
                  "example": "e" * 30, "evidenceIds": [pack["evidences"][0]["id"]]},
             ]},
            ["R"], evidence_pack=pack,
        )
    monkeypatch.setattr(svc, "compose_with_llm", fake_compose)
    out = await svc.run_compose(roles_raw=["R"], evidence_pack=pack, use_workbench_llm=False)
    assert out["mode"] == "journal"
    assert out["evidencePack"]["count"] >= 1
    assert all(k.get("evidenceIds") for k in out["knowledge"])
```

- [ ] **Step 2: 实现 `run_compose`**

- 入参：`packId`（从 history 取）或 `evidence_pack` / `evidences`  
- `selected_evidences`；若 `<5` 且 deep 路径，返回 400 语义错误 dict（路由转 400）  
- 调 `compose_with_llm`；失败则 `build_cards` + `mode: cached` + 保留 pack  
- 写 history：`mode: journal`，带 cover/knowledge/evidencePack  

- [ ] **Step 3: 改写 `run_scan`**

```python
async def run_scan(...):
    researched = await run_research(..., depth="shallow", ...)
    pack = researched.get("evidencePack")
    composed = await run_compose(..., evidence_pack=pack, pack_id=researched.get("id"), ...)
    # keep mode "ai" when LLM ok for旧 UI；也可 journal
    return composed
```

注意：避免 research+compose **双写两条 history**。做法：research 在 scan 路径传 `persist=False`，或 compose 更新同一 `id`。推荐：

```python
researched = await run_research(..., persist=False)
composed = await run_compose(..., evidence_pack=..., persist=True)
```

- [ ] **Step 4: 路由**

```python
app.router.add_post("/api/cards/compose", compose)
```

compose handler：解析 packId / evidences / evidenceIdsAllowed（把未允许的 `selected=False`）。

- [ ] **Step 5: 跑测试**

Run:  
`PYTHONPATH=src python3 -m pytest tests/workbench/test_knowledge_journal.py tests/workbench/test_knowledge_cards.py -q`  
Expected: PASS（旧 scan 测试仍绿）

- [ ] **Step 6: Commit**

```bash
git commit -am "feat(cards): compose API; scan becomes shallow research+compose"
```

---

### Task 6: 工坊 UI（深采 / 成刊 / 台账 / 快扫）

**Files:**
- Modify: `src/cn_social_agent/workbench/index.html`（卡片工具栏区域，约 `mode=card` 控件）
- Modify: `src/cn_social_agent/workbench/cards_workshop.js`

- [ ] **Step 1: HTML**

在原 `kcScanBtn` 旁改为：

```html
<button type="button" id="kcResearchBtn" class="btn primary">深采</button>
<button type="button" id="kcComposeBtn" class="btn soft" disabled>成刊</button>
<button type="button" id="kcScanBtn" class="btn secondary sm">快扫</button>
```

增加素材台账容器：

```html
<details id="kcEvidencePanel" class="kc-evidence-panel">
  <summary>本期素材 <span id="kcEvidenceCount">0</span></summary>
  <div id="kcEvidenceList"></div>
</details>
```

- [ ] **Step 2: JS 状态**

```javascript
let evidencePack = { evidences: [], count: 0 };
let packId = "";

function renderEvidenceList() {
  const list = $("#kcEvidenceList");
  const n = (evidencePack.evidences || []).filter(e => e.selected !== false).length;
  $("#kcEvidenceCount").textContent = String(n);
  $("#kcComposeBtn").disabled = n < 5;
  list.innerHTML = (evidencePack.evidences || []).map(e => `
    <label class="kc-ev-row">
      <input type="checkbox" data-eid="${e.id}" ${e.selected === false ? "" : "checked"} />
      <span class="kc-ev-score">${e.score}</span>
      <span class="kc-ev-text">${escapeHtml(e.text.slice(0, 100))}</span>
    </label>`).join("");
}

async function researchDeep() {
  setStatus("采编中…");
  const data = await api("/api/cards/research", { method: "POST", body: JSON.stringify({
    roles: parseRolesInput(), category: currentCategory, appendPackId: packId || undefined, edition: editionInput()
  })});
  evidencePack = data.evidencePack || { evidences: [], count: 0 };
  packId = data.packId || data.id || "";
  renderEvidenceList();
  setStatus(evidencePack.count ? `素材就绪（${evidencePack.count} 条）` : (data.error || "无可用证据"));
}

async function composeJournal() {
  setStatus("成刊中…");
  // sync checkboxes → selected
  const data = await api("/api/cards/compose", { method: "POST", body: JSON.stringify({
    packId, evidences: evidencePack.evidences, roles: parseRolesInput(),
    category: currentCategory, edition: editionInput()
  })});
  applyPayload(data);
  evidencePack = data.evidencePack || evidencePack;
  setStatus(`第 ${data.edition || ""} 期已生成`);
}
```

- 原 `scan()` 文案改为「快扫中…」，成功提示去掉「深度生成」  
- `applyPayload` / 历史回载：若有 `evidencePack` 则恢复台账  
- 单卡编辑区：渲染 `evidenceIds` 芯片，点击 `alert`/popover 显示原文  

- [ ] **Step 3: 手动冒烟**

1. 登录 demo → 知识卡片  
2. 深采 → 台账 ≥1 且无拼音词典  
3. 成刊（或证据不足时按钮禁用）  
4. 快扫仍能出卡  

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(cards): workshop research/compose UI and evidence ledger"
```

---

### Task 7: InsForge / cloud 尽力持久化 + 收尾测试

**Files:**
- Modify: `src/cn_social_agent/cards/cloud.py`
- Modify: `tests/workbench/test_knowledge_journal.py`

- [ ] **Step 1: upsert 增加 `evidence_pack` 字段**

```python
row = {
  ...
  "evidence_pack": rec.get("evidencePack") or {},
}
# on error mentioning unknown column: retry without evidence_pack; persisted local
```

- [ ] **Step 2: API 串联测试（mock LLM + scrape）**

在 `test_knowledge_cards.py` 的 aiohttp 客户端夹具风格下，增加：

```python
async def test_research_compose_http(client, monkeypatch):
    # login → research (mock scan_roles) → compose (mock compose_with_llm) → history has evidencePack
    ...
```

- [ ] **Step 3: 全量相关测试**

Run:  
`PYTHONPATH=src python3 -m pytest tests/workbench/test_knowledge_journal.py tests/workbench/test_knowledge_cards.py -q`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(cards): persist evidence packs to cloud when schema allows"
```

---

## Spec coverage checklist

| Spec 要求 | Task |
|-----------|------|
| 深采 6–8 query、早停 18/30 | Task 2 |
| Evidence schema / 打分过滤 | Task 1–2 |
| research / compose API | Task 3–5 |
| 快扫 = 浅 research+compose | Task 5 |
| 3–6 卡灵活 kind、证据 ID | Task 4 |
| 台账勾选、深采/成刊 UI | Task 6 |
| history + InsForge pack | Task 3、7 |
| 无证据不贴词典 marketNote | Task 1、4（pick_market_note） |
| 旧 scan 兼容 | Task 5 + 回归测试 |

## Placeholder / consistency notes

- Pack 主键对外统一用 history `id` 作为 `packId`（不另建 packs 表）  
- `scan_roles` 深采返回 **structured rows**；`build_pack` 统一入口  
- `run_research(..., persist=False)` 供 scan 避免双写  

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-12-knowledge-journal.md`.

**两种执行方式：**

1. **Subagent-Driven（推荐）** — 每任务新开子代理，任务间复核  
2. **Inline Execution** — 本会话按计划连续做，设检查点  

你要哪一种？
