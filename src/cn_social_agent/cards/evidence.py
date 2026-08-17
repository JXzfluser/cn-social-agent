"""Evidence pack: score, dedupe, merge, citation validation."""

from __future__ import annotations

import re
from typing import Any

# Shared base vocabulary — works across categories
_BASE_SIGNAL = (
    r"能力|方法|实践|案例|流程|步骤|场景|价值|落地|交付|架构|框架|系统|工具"
    r"|模型|API|SDK|开源|性能|优化|算法|工作流|知识库|检索|部署"
)

_CATEGORY_SIGNALS: dict[str, str] = {
    "hiring_insight": (
        r"招聘|岗位|职责|任职|要求|技能|经验|JD|工程师|开发|面试"
        r"|Agent|RAG|LLM|LangGraph|向量|编排|工具调用|Prompt|微调|全栈|独立开发"
        r"|训练|推理|蒸馏|强化学习|参数|数据集|基准|评测|显存|量化|上下文|多模态|开源模型"
    ),
    "product_explain": (
        r"产品|功能|用户|痛点|上手|教程|竞品|亮点|操作|工作流|适用|边界"
        r"|FAQ|最佳实践|交付物|输入|产出|演示|界面|体验|转化|留存"
    ),
    "skill_roadmap": (
        r"学习|入门|进阶|练习|里程碑|教程|过关|技能树|项目|作业|实战"
        r"|心智模型|壁垒|难点|书单|课程|考核|阶段|从零到一|必学"
    ),
    "industry_brief": (
        r"趋势|市场|投融资|融资|估值|政策|监管|合规|格局|玩家|竞争"
        r"|热点|机会|挑战|风险|指标|观察|企业|应用|动态|分析|观点"
    ),
}

# Back-compat alias used by older imports / tests
SIGNAL_RE = re.compile(
    _BASE_SIGNAL + r"|" + _CATEGORY_SIGNALS["hiring_insight"],
    re.I,
)

# Dictionary / encyclopedia / nav-site noise
JUNK_RE = re.compile(
    r"拼音|注音|ㄉ|ㄌ|汉语词语|百度百科|名词、动词|褒义词|解释是[:：]"
    r"|怎么养成独立|为什么要独立|自己动手丰衣足食|涵盖所有领域知识"
    r"|单独站立|孤立无所依靠|不依附他者"
    r"|工具集官网|收录了国内外数百个|导航网站包括"
    r"|即梦AI|Seedance|免费AI工具|AIGC\s*工具导航|汇聚全网最全"
    r"|个\s*AI\s*工具和|AI\s*网站和\s*AI\s*工具|工具导航大全|AI\s*Tools\s*Directory"
    r"|豆包\s*是你的\s*AI|登录即可免费使用|AI写作\s*工具[、,，]\s*AI绘画",
    re.I,
)

# SERP / page-chrome fragments that sneak into snippet text.
# NOTE: site-name suffixes like "-CSDN博客" are stripped in clean_snippet_text
# instead of rejecting the whole snippet — CSDN/知乎 articles are valid evidence.
SERP_NOISE_RE = re.compile(
    r'(clamp|isPc|summarySpan|pageStyleUpgrade|consistencyUpgrade|'
    r'"styles"|sc-image-rounded|html>|</?\w{1,12}>|'
    r"知乎\s*[播报]|OSCHINA\.\.\.|博客\s*xAI\s*的破局)",
    re.I,
)


def clean_snippet_text(text: str, *, max_len: int = 400) -> str:
    """Strip SERP chrome / HTML debris before packing or scoring."""
    t = str(text or "")
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r'[{}\[\]"]+', " ", t)
    t = re.sub(
        r"\b(clamp|isPc|summarySpan|pageStyleUpgrade|consistencyUpgrade|isSingleLine)\b",
        " ",
        t,
        flags=re.I,
    )
    t = re.sub(r"[:：]\s*\d+\b", " ", t)  # leftover :2 from JSON
    # Strip site-name suffixes / prefixes (keep the article text itself)
    t = re.sub(r"[-_|·]\s*(CSDN博客|简书|博客园|掘金|知乎专栏|腾讯云开发者社区)\S*", " ", t)
    t = re.sub(r"来自[:：]\s*\S{1,20}(官方教程|官方博客)?", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" ,;:：")
    return t[:max_len]


def looks_like_serp_noise(text: str) -> bool:
    t = str(text or "").strip()
    if not t:
        return False
    if SERP_NOISE_RE.search(t):
        return True
    if re.search(r"[:：]\s*(true|false|\d+)\b", t, re.I) and len(t) < 80:
        return True
    # High density of ASCII punctuation / JSON leftovers
    junk_chars = len(re.findall(r"[{}\[\]\"\\=]", t))
    return junk_chars >= 6 and junk_chars >= len(t) * 0.08


_SIGNAL_CACHE: dict[str, re.Pattern[str]] = {}


def signal_re_for(category: str = "hiring_insight") -> re.Pattern[str]:
    cid = (category or "hiring_insight").strip() or "hiring_insight"
    if cid not in _SIGNAL_CACHE:
        extra = _CATEGORY_SIGNALS.get(cid) or _CATEGORY_SIGNALS["hiring_insight"]
        _SIGNAL_CACHE[cid] = re.compile(_BASE_SIGNAL + r"|" + extra, re.I)
    return _SIGNAL_CACHE[cid]


def _signal_hits(text: str, *, role: str = "", category: str = "hiring_insight") -> int:
    sig = signal_re_for(category)
    hits = len(sig.findall(text))
    if role:
        # Prefer whole-role mention over first character (独立 ≠ 独立开发者)
        if role in text:
            hits += 2
        elif len(role) >= 4 and role[:2] in text and role[2:] in text:
            hits += 1
    return hits


def is_useful_snippet(
    text: str, *, role: str = "", min_len: int = 32, category: str = "hiring_insight"
) -> bool:
    """Reject dictionary glosses; prefer category-aware signal-rich snippets."""
    t = clean_snippet_text(text or "")
    if len(t) < min_len:
        return False
    if JUNK_RE.search(t):
        return False
    if looks_like_serp_noise(t):
        return False
    if re.search(r"^[\u4e00-\u9fff]{1,4}（拼音", t):
        return False
    return _signal_hits(t, role=role, category=category) >= 2


def score_snippet(
    text: str, *, role: str = "", category: str = "hiring_insight"
) -> tuple[float, list[str]]:
    t = clean_snippet_text(text or "")
    # Pack scoring allows shorter JD lines than scrape's market-note filter (32).
    if not is_useful_snippet(t, role=role, min_len=20, category=category):
        return 0.0, []
    sig = signal_re_for(category)
    signals = list(dict.fromkeys(sig.findall(t)))
    score = float(len(signals))
    if role and role in t:
        score += 2.0
    score += min(len(t) / 200.0, 1.5)
    return score, signals[:8]


def build_pack(
    raw_items: list[dict[str, Any]],
    *,
    limit: int = 40,
    category: str = "hiring_insight",
) -> dict[str, Any]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for item in raw_items:
        text = clean_snippet_text(str(item.get("text") or ""))
        if looks_like_serp_noise(text):
            continue
        role = str(item.get("role") or "")
        sc, signals = score_snippet(text, role=role, category=category)
        # Seed rows come from a chosen source (Agent/hotspot handoff): keep
        # them even when signal-light, and rank them above scraped top-ups.
        is_seed = str(item.get("engine") or "") == "seed"
        if is_seed:
            if sc <= 0 and len(text) >= 40:
                sc = 1.0
            if sc > 0:
                sc += 10.0
        # Top-up rows that already passed the topic-relevance gate are on
        # subject; keep them even if they lack generic signal words.
        elif item.get("relevant") and sc <= 0 and len(text) >= 20:
            sc = 1.0
        if sc <= 0 or text in seen:
            continue
        seen.add(text)
        row = {
            "text": text,
            "query": str(item.get("query") or "")[:120],
            "engine": str(item.get("engine") or "")[:16],
            "role": role[:40],
            "score": round(sc, 2),
            "signals": signals,
            "url": str(item.get("url") or "")[:200],
            "title": str(item.get("title") or "")[:80],
            "selected": True,
        }
        # Preserve the gate flag so a re-pack (e.g. merge_packs) re-floors it.
        if item.get("relevant"):
            row["relevant"] = True
        rows.append(row)
    rows.sort(key=lambda e: e["score"], reverse=True)
    rows = rows[:limit]
    for i, e in enumerate(rows, 1):
        e["id"] = f"e{i}"
    return {"evidences": rows, "count": len(rows)}


def merge_packs(
    a: dict[str, Any] | None,
    b: dict[str, Any] | None,
    *,
    limit: int = 40,
    category: str = "hiring_insight",
) -> dict[str, Any]:
    raw: list[dict[str, Any]] = []
    for pack in (a, b):
        for e in (pack or {}).get("evidences") or []:
            raw.append(e)
    selected_map = {e["text"]: e.get("selected", True) for e in raw if e.get("text")}
    existing_ids = {
        str(e.get("text") or ""): str(e.get("id") or "")
        for e in (a or {}).get("evidences") or []
        if e.get("text") and e.get("id")
    }
    used_ids = set(existing_ids.values())
    next_id = max(
        (
            int(m.group(1))
            for eid in used_ids
            if (m := re.fullmatch(r"e(\d+)", eid))
        ),
        default=0,
    ) + 1
    pack = build_pack(raw, limit=limit, category=category)
    for e in pack["evidences"]:
        e["selected"] = selected_map.get(e["text"], True)
        if e["text"] in existing_ids:
            e["id"] = existing_ids[e["text"]]
            continue
        while f"e{next_id}" in used_ids:
            next_id += 1
        e["id"] = f"e{next_id}"
        used_ids.add(e["id"])
        next_id += 1
    return pack


def selected_evidences(pack: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [e for e in (pack or {}).get("evidences") or [] if e.get("selected", True)]


def _card_tokens(card_text: str) -> list[str]:
    """Tokenize for citation grounding — ASCII words + CJK bigrams."""
    text = str(card_text or "")
    tokens = [t for t in re.split(r"\W+", text) if len(t) >= 2]
    cjk = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    for chunk in cjk:
        tokens.append(chunk)
        if len(chunk) >= 4:
            tokens.extend(chunk[i : i + 2] for i in range(0, len(chunk) - 1, 2))
    # Dedup, keep order, prefer longer first for ranking later
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out[:24]


def _token_overlap(tokens: list[str], evidence_text: str) -> int:
    if not tokens:
        return 0
    et = evidence_text or ""
    return sum(1 for t in tokens if t in et)


def validate_evidence_ids(
    ids: list[str] | None,
    pack: dict[str, Any] | None,
    *,
    card_text: str = "",
    min_count: int = 1,
) -> list[str]:
    """Keep valid ids; backfill only when card tokens overlap evidence text.

    Never silently attach the highest-score snippet with zero overlap — that
    produced fake citations on hollow journals.
    """
    selected = selected_evidences(pack)
    if not selected:
        return []
    by_id = {e["id"]: e for e in selected}
    out = [i for i in (ids or []) if i in by_id]
    if len(out) >= min_count:
        return out[:4]
    tokens = _card_tokens(card_text)
    if not tokens:
        return out[:4]
    ranked = sorted(
        selected,
        key=lambda e: (_token_overlap(tokens, str(e.get("text") or "")), e.get("score", 0)),
        reverse=True,
    )
    for e in ranked:
        if e["id"] in out:
            continue
        if _token_overlap(tokens, str(e.get("text") or "")) <= 0:
            continue
        out.append(e["id"])
        if len(out) >= min_count:
            break
    return out[:4]
