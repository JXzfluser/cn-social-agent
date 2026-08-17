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


_VALID_FRESHNESS = frozenset({"hot", "rising", "steady"})


def infer_freshness(source: str) -> str:
    src = str(source or "").strip().lower()
    if src in ("hn", "v2ex", "lobsters", "sspai"):
        return "hot"
    if src == "github":
        return "rising"
    return "steady"


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
    fr = str(out.get("freshness") or "").strip().lower()
    if fr not in _VALID_FRESHNESS:
        out["freshness"] = infer_freshness(str(out.get("source") or ""))
    out["score"] = score_item(out)
    out["why"] = build_why(out)
    out["handoff"] = {
        "default_track": "presentation" if out["source"] == "github" else "koubo",
        "research_seed": out["why"],
    }
    return out


def _topic_key_for_item(item: dict[str, Any]) -> str:
    key = str(item.get("topic_key") or "").strip()
    if key:
        return key
    title = str(item.get("title") or item.get("full_name") or "")
    return make_topic_key(title) or make_topic_key(str(item.get("url") or "")) or ""


def dedupe_by_topic_key(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    passthrough: list[dict[str, Any]] = []
    for it in items:
        key = _topic_key_for_item(it)
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


async def attach_local_assets(
    board: list[dict[str, Any]], *, limit_lookup: int = 3
) -> list[dict[str, Any]]:
    """Best-effort: match each topic_key via lookup_local_assets."""
    from cn_social_agent.knowledge.assets import lookup_local_assets

    out: list[dict[str, Any]] = []
    for item in board:
        row = dict(item)
        q = str(row.get("topic_key") or row.get("title") or row.get("full_name") or "")[:80]
        if not q:
            out.append(row)
            continue
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
        except Exception:  # noqa: BLE001 — best-effort collision
            pass
        out.append(row)
    return out
