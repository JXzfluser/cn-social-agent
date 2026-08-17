# 热点选题引擎 v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Agent hotspots into a scored, filterable, handoff-capable选题引擎（A 质量 + B 中文源 + C 研究并交接）.

**Architecture:** Keep fetchers in `tools/hotspots.py`; add pure helpers (`score`, `domain`, `dedupe`, `why`) in `tools/hotspot_ rank.py` (or `hotspot_engine.py`); enrich board after scan; extend `GET /api/hotspots`; add `POST /api/hotspots/handoff` + shared handoff helper; wire Agent drawer UI.

**Tech Stack:** Python 3.12, aiohttp, httpx, existing `topic_key` / `lookup_topic_assets` / `fetch_url_text`, Workbench `index.html`.

**Spec:** `docs/superpowers/specs/2026-08-16-hotspot-engine-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| Create: `src/cn_social_agent/tools/hotspot_engine.py` | score / domain / why / dedupe / enrich board |
| Modify: `src/cn_social_agent/tools/hotspots.py` | call engine after fetch; sspai RSS; `domain` param |
| Create: `src/cn_social_agent/tools/hotspot_handoff.py` | build research_notes + propose_* payloads |
| Modify: `src/cn_social_agent/api/hotspots_routes.py` | `domain` query; POST handoff |
| Modify: `src/cn_social_agent/tools/builtin.py` | `domain` on scan tool; register `handoff_hotspot` |
| Modify: `src/cn_social_agent/workbench/index.html` | why / assets / domain / handoff UI |
| Create: `tests/workbench/test_hotspot_engine.py` | unit tests |
| Create: `tests/workbench/test_hotspot_handoff.py` | handoff unit tests |

---

### Task 1: Scoring + why + topic_key + dedupe (S1 core)

**Files:**
- Create: `src/cn_social_agent/tools/hotspot_engine.py`
- Create: `tests/workbench/test_hotspot_engine.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/workbench/test_hotspot_engine.py
from cn_social_agent.tools.hotspot_engine import (
    assign_domains,
    build_why,
    dedupe_by_topic_key,
    heat_norm,
    score_item,
)


def test_heat_norm_monotonic():
    assert heat_norm(0, source="hn") < heat_norm(100, source="hn")
    assert 0 <= heat_norm(50, source="github") <= 100


def test_assign_domains_ai():
    assert "ai" in assign_domains("New LLM Agent framework", "")


def test_dedupe_keeps_higher_score():
    a = {"title": "Foo Bar", "full_name": "Foo Bar", "score": 40, "source": "hn"}
    b = {"title": "Foo Bar", "full_name": "Foo Bar", "score": 80, "source": "github"}
    out = dedupe_by_topic_key([a, b])
    assert len(out) == 1
    assert out[0]["score"] == 80


def test_build_why_github():
    why = build_why({"source": "github", "language": "Python", "local_assets": None})
    assert "高星" in why or "适合" in why
```

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

Run: `.venv/bin/python -m pytest tests/workbench/test_hotspot_engine.py -q`

- [ ] **Step 3: Implement `hotspot_engine.py`**

```python
# src/cn_social_agent/tools/hotspot_engine.py
"""Score / domain / why / dedupe for hotspot board items."""
from __future__ import annotations
import math
import re
from typing import Any
from cn_social_agent.knowledge.topic_key import topic_key as make_topic_key

_DOMAIN_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("ai", re.compile(r"\b(ai|llm|gpt|agent|openai|模型|智能体|大模型)\b", re.I)),
    ("devtools", re.compile(r"\b(cli|sdk|ide|git|docker|框架|编译|devtools?)\b", re.I)),
    ("product", re.compile(r"\b(saas|product|ux|增长|独立开发|产品)\b", re.I)),
    ("hiring", re.compile(r"\b(招聘|面试|岗位|jd|hiring)\b", re.I)),
]

def heat_norm(raw: float, *, source: str) -> float:
    x = max(0.0, float(raw or 0))
    # log scale; github stars often larger
    base = math.log1p(x) / math.log1p(5000 if source == "github" else 500)
    return max(0.0, min(100.0, base * 100.0))

def assign_domains(title: str, description: str = "") -> list[str]:
    text = f"{title or ''} {description or ''}"
    hits = [d for d, pat in _DOMAIN_RULES if pat.search(text)]
    return hits or ["general"]

def freshness_bonus(source: str, freshness: str = "hot") -> float:
    if freshness == "hot" or source in ("hn", "v2ex", "lobsters"):
        return 80.0
    if freshness == "rising" or source == "github":
        return 70.0
    return 50.0

def fit_bonus(domains: list[str]) -> float:
    if not domains or domains == ["general"]:
        return 50.0
    return 75.0

def score_item(item: dict[str, Any]) -> float:
    src = str(item.get("source") or "")
    heat = heat_norm(float(item.get("raw_score") or item.get("stars") or 0), source=src)
    domains = item.get("domains") or assign_domains(
        str(item.get("title") or item.get("full_name") or ""),
        str(item.get("description") or ""),
    )
    fr = str(item.get("freshness") or "hot")
    return round(0.55 * heat + 0.25 * freshness_bonus(src, fr) + 0.20 * fit_bonus(domains), 2)

def build_why(item: dict[str, Any]) -> str:
    src = str(item.get("source") or "")
    lang = str(item.get("language") or item.get("meta") or "").strip()
    if src == "github":
        why = f"近创高星 · {lang or '开源'} · 适合讲「是什么+谁该用」"
    elif src in ("hn", "lobsters", "devto"):
        why = "社区热议 · 适合观点/对比角"
    elif src in ("v2ex", "sspai"):
        why = "中文讨论热 · 适合本地受众口播"
    else:
        why = "热点选题 · 适合做成内容"
    assets = item.get("local_assets")
    if isinstance(assets, dict) and (
        (assets.get("journal_count") or 0) + (assets.get("video_count") or 0) > 0
    ):
        why += " · 本地已有资产，可续做或换角"
    return why[:48]

def enrich_item(item: dict[str, Any]) -> dict[str, Any]:
    out = dict(item)
    title = str(out.get("title") or out.get("full_name") or "")
    out.setdefault("title", title)
    out.setdefault("full_name", title)
    out["topic_key"] = make_topic_key(title) or make_topic_key(out.get("url") or "") or ""
    out["raw_score"] = float(out.get("raw_score") or out.get("stars") or 0)
    out["domains"] = assign_domains(title, str(out.get("description") or ""))
    out.setdefault("freshness", "hot")
    out["score"] = score_item(out)
    out["why"] = build_why(out)
    out["handoff"] = {
        "default_track": "presentation" if out["source"] == "github" else "koubo",
        "research_seed": out["why"],
    }
    return out

def dedupe_by_topic_key(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    passthrough: list[dict[str, Any]] = []
    for it in items:
        key = str(it.get("topic_key") or "").strip()
        if not key:
            passthrough.append(it)
            continue
        prev = best.get(key)
        if prev is None or float(it.get("score") or 0) > float(prev.get("score") or 0):
            best[key] = it
    merged = list(best.values()) + passthrough
    merged.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    for i, it in enumerate(merged, start=1):
        it["rank"] = i
        src_label = it.get("source_label") or it.get("source") or ""
        title = it.get("full_name") or it.get("title") or ""
        score = it.get("score")
        it["headline"] = f"#{i} [{src_label}] {title}" + (f" · {score}" if score else "")
    return merged

def enrich_board(board: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return dedupe_by_topic_key([enrich_item(x) for x in board if isinstance(x, dict)])

DOMAIN_OPTIONS = [
    {"id": "all", "label": "全部"},
    {"id": "ai", "label": "AI"},
    {"id": "devtools", "label": "开发工具"},
    {"id": "product", "label": "产品"},
    {"id": "hiring", "label": "招聘"},
]

def filter_by_domain(board: list[dict[str, Any]], domain: str) -> list[dict[str, Any]]:
    d = (domain or "all").strip().lower()
    if d in ("", "all"):
        return board
    out = [x for x in board if d in (x.get("domains") or [])]
    for i, it in enumerate(out, start=1):
        it["rank"] = i
    return out
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `.venv/bin/python -m pytest tests/workbench/test_hotspot_engine.py -q`

- [ ] **Step 5: Commit** (only if user asked to commit; otherwise skip)

---

### Task 2: Wire engine into scan + API + UI why (S1 complete)

**Files:**
- Modify: `src/cn_social_agent/tools/hotspots.py` (end of `tool_scan_hotspot_board`)
- Modify: `src/cn_social_agent/api/hotspots_routes.py`
- Modify: `src/cn_social_agent/workbench/index.html` (hotspot chip render)
- Modify: `src/cn_social_agent/tools/builtin.py` (`domain` param on `scan_hotspot_board`)

- [ ] **Step 1: After aggregating `board` in `tool_scan_hotspot_board`, enrich + filter**

```python
from cn_social_agent.tools.hotspot_engine import (
    DOMAIN_OPTIONS,
    enrich_board,
    filter_by_domain,
)

# ... after building board from sources, before return:
board = enrich_board(board)
board = filter_by_domain(board, domain)  # add domain: str = "all" param
board = board[:per_page]
# re-rank already done in enrich/filter
return {
    "ok": True,
    "title": title,
    "source": src,
    "domain": domain or "all",
    "domains": DOMAIN_OPTIONS,
    "sources": list_hotspot_sources(),
    "count": len(board),
    "board": board,
    "scored": True,
    "errors": errors,
    "hint": "...",
}
```

Accept `source` ids still exclude `sspai` until Task 4.

- [ ] **Step 2: API passes `domain` query**

```python
domain = (q.get("domain") or "all").strip().lower() or "all"
data = await tool_scan_hotspot_board(..., source=source, domain=domain)
```

- [ ] **Step 3: UI chip shows `why`**

In `loadHotspots` / chip builder, after headline:

```javascript
const why = escapeHtml(item.why || "");
// inside chip HTML:
why ? `<div class="meta hotspot-why">${why}</div>` : ""
```

Pass `domain` from a new `<select id="hotspotDomain">` into `/api/hotspots?...&domain=`.

- [ ] **Step 4: Smoke test**

Run: `.venv/bin/python -m pytest tests/workbench/test_hotspot_engine.py -q`  
Manual: open Agent → 热点 → chips show why line.

---

### Task 3: local_assets collision + domain filter polish (S2)

**Files:**
- Modify: `src/cn_social_agent/tools/hotspot_engine.py` — `attach_local_assets`
- Modify: `src/cn_social_agent/tools/hotspots.py` — call attach when user ctx available
- Modify: `src/cn_social_agent/api/hotspots_routes.py` — after scan, enrich with user assets
- Modify: `src/cn_social_agent/workbench/index.html` — asset badge + domain select

- [ ] **Step 1: Test attach refreshes why**

```python
def test_build_why_with_assets():
    why = build_why({
        "source": "hn",
        "local_assets": {"journal_count": 1, "video_count": 0},
    })
    assert "本地已有资产" in why
```

- [ ] **Step 2: Implement attach helper**

```python
async def attach_local_assets(board: list[dict[str, Any]], *, limit_lookup: int = 3) -> list[dict[str, Any]]:
    """Best-effort: match each topic_key via lookup_local_assets."""
    from cn_social_agent.knowledge.assets import lookup_local_assets
    out = []
    for item in board:
        row = dict(item)
        q = str(row.get("topic_key") or row.get("title") or "")[:80]
        try:
            hit = await lookup_local_assets(q, limit=limit_lookup)
            hits = hit.get("hits") or []
            if hits:
                h0 = hits[0]
                row["local_assets"] = {
                    "journal_count": h0.get("journal_count") or 0,
                    "video_count": h0.get("video_count") or 0,
                    "hint": hit.get("hint") or "",
                    "topic_key": h0.get("topic_key"),
                }
                row["why"] = build_why(row)
        except Exception:
            pass
        out.append(row)
    return out
```

Call from `get_hotspots` **after** `tool_scan_hotspot_board` (has user session via `require_user` + tool context). Ensure `set_tool_context` is set in request path like other routes (mirror `assets_routes` / chat).

- [ ] **Step 3: UI badge**

```javascript
const assets = item.local_assets || {};
const assetTag = ((assets.journal_count||0)+(assets.video_count||0)) > 0
  ? `<span class="src">已有资产</span>` : "";
```

Add domain `<select>` next to source buttons; on change reload hotspots.

---

### Task 4: Chinese RSS source `sspai` (S3)

**Files:**
- Modify: `src/cn_social_agent/tools/hotspots.py`
- Test: `tests/workbench/test_hotspot_sspai.py` with XML fixture

- [ ] **Step 1: Fixture + parser test**

```python
SAMPLE = """<?xml version="1.0"?>
<rss><channel>
<item><title>AI 工具盘点</title><link>https://sspai.com/x</link><description>desc</description></item>
</channel></rss>"""

def test_parse_rss_items():
    from cn_social_agent.tools.hotspots import parse_rss_items
    items = parse_rss_items(SAMPLE)
    assert items[0]["title"] == "AI 工具盘点"
```

- [ ] **Step 2: Implement `_scan_sspai`**

```python
import os
import xml.etree.ElementTree as ET

DEFAULT_CN_RSS = "https://sspai.com/feed"

def parse_rss_items(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    items = []
    for node in root.findall(".//item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        desc = (node.findtext("description") or "").strip()
        if title:
            items.append({"title": title, "url": link, "description": desc[:160]})
    return items

async def _scan_sspai(*, per_page: int) -> dict[str, Any]:
    url = (os.getenv("HOTSPOT_CN_RSS_URL") or DEFAULT_CN_RSS).strip()
    try:
        async with httpx.AsyncClient(timeout=12.0, trust_env=True, headers={"User-Agent": "cn-social-agent"}) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                return {"ok": False, "source": "sspai", "error": f"RSS {resp.status_code}", "board": []}
            rows = parse_rss_items(resp.text)[:per_page]
    except Exception as exc:
        return {"ok": False, "source": "sspai", "error": str(exc)[:200], "board": []}
    board = [
        _board_item(rank=i, source="sspai", source_label="少数派", title=r["title"], url=r["url"],
                    meta="少数派", description=r.get("description") or "", score=max(1, 100 - i))
        for i, r in enumerate(rows, start=1)
    ]
    return {"ok": True, "source": "sspai", "title": "少数派 RSS", "board": board}
```

Add to `SOURCES`, `tool_scan_hotspot_board` branches, UI source button `少数派`.

- [ ] **Step 3: Tests pass offline with fixture; live optional**

---

### Task 5: Handoff API + tool + UI (S4)

**Files:**
- Create: `src/cn_social_agent/tools/hotspot_handoff.py`
- Create: `tests/workbench/test_hotspot_handoff.py`
- Modify: `src/cn_social_agent/api/hotspots_routes.py`
- Modify: `src/cn_social_agent/tools/builtin.py`
- Modify: `src/cn_social_agent/workbench/index.html`

- [ ] **Step 1: Failing tests for payload shape**

```python
import asyncio
from cn_social_agent.tools.hotspot_handoff import build_handoff_payload

def test_handoff_koubo_shape():
    out = asyncio.get_event_loop().run_until_complete(
        build_handoff_payload(
            title="Test Topic",
            url="https://example.com",
            source="hn",
            why="社区热议",
            track="koubo",
            research_notes="已有笔记",
        )
    )
    assert out["ok"] is True
    assert out["track"] == "koubo"
    assert out["propose_short_video"] is True
    assert "社区热议" in out["research_notes"]
```

- [ ] **Step 2: Implement handoff helper**

```python
# hotspot_handoff.py
async def build_handoff_payload(
    *, title: str, url: str, source: str = "", why: str = "",
    topic_key: str = "", track: str = "koubo", research_notes: str = "",
) -> dict:
    track = (track or "koubo").strip().lower()
    if track not in ("koubo", "presentation", "journal"):
        return {"ok": False, "error": "track must be koubo|presentation|journal"}
    title = (title or "").strip()
    if not title:
        return {"ok": False, "error": "title required"}
    notes = (research_notes or "").strip()
    if not notes and url:
        try:
            from cn_social_agent.tools.builtin import tool_fetch_url_text  # or actual fetch helper
            fetched = await tool_fetch_url_text(url=url)  # adjust to real signature
            notes = str((fetched or {}).get("text") or (fetched or {}).get("content") or "")[:2000]
        except Exception as exc:
            notes = f"(抓取失败: {exc})"
    bundle = f"为何值得做：{why}\n来源：{source}\n链接：{url}\n\n{notes}".strip()
    base = {
        "ok": True,
        "track": track,
        "topic": title,
        "topic_key": topic_key,
        "research_notes": bundle,
        "why": why,
        "url": url,
    }
    if track == "koubo":
        return {**base, "propose_short_video": True, "content_angle": "intro", "seconds": 120}
    if track == "presentation":
        return {
            **base,
            "propose_presentation": True,
            "auto_draft": True,
            "needs_deep_draft": True,
            "aspect": "9:16",
            "theme": "talent-map",
        }
    return {**base, "propose_cards": True, "roles": [title]}
```

Resolve real `fetch_url_text` function name from `tools/builtin.py` / scrape helpers before coding.

- [ ] **Step 3: Route**

```python
@require_user
async def post_hotspot_handoff(request):
    body = await request.json()
    out = await build_handoff_payload(**{...})
    return web.json_response(out, status=200 if out.get("ok") else 400)

# setup:
app.router.add_post("/api/hotspots/handoff", post_hotspot_handoff)
```

- [ ] **Step 4: UI**

Primary button on chip → modal/select: 口播 / 讲解 / 期刊 → `POST /api/hotspots/handoff` → call existing:

- koubo: `appendVideoCard` / open video track with topic + notes  
- presentation: `openPresentationFromAgent(out)`  
- journal: `openCardWorkshop` / propose cards path  

Keep secondary「洞察研究」as chat-only starter.

- [ ] **Step 5: Register `handoff_hotspot` tool** wrapping same helper.

- [ ] **Step 6: Full regression**

```bash
.venv/bin/python -m pytest tests/workbench/test_hotspot_engine.py tests/workbench/test_hotspot_handoff.py tests/workbench/test_hotspot_sspai.py -q
```

---

### Task 6: Spec status + Skill hint (docs)

**Files:**
- Modify: `docs/superpowers/specs/2026-08-16-hotspot-engine-design.md` — Status already Approved
- Optional: one line in Agent loop system hint that `scan_hotspot_board` returns scored board with `why`

- [ ] **Step 1: Confirm health path still works; restart workbench if needed for UI**

---

## Spec coverage check

| Spec section | Task |
|--------------|------|
| A score/why/dedupe/topic_key | T1–T2 |
| A local_assets | T3 |
| B domain filter | T2–T3 |
| B sspai RSS | T4 |
| C handoff API/UI/tool | T5 |
| Non-goals D / crawlers | — skipped |
| PH optional | — deferred per spec |

## Placeholder scan

No TBD steps; fetch helper name must be resolved against codebase in T5 Step 2 (explicit action, not a placeholder).

---

## Execution

Plan saved to `docs/superpowers/plans/2026-08-16-hotspot-engine.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — implement in this session with checkpoints  

Which approach?
