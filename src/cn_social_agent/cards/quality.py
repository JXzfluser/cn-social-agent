"""Journal / knowledge-card quality gate (成刊 depth bars).

Mirrors presentation ``depth_report``: soft prompt rules become pass/fail checks
so hollow or truncated journals cannot claim「稿件完成」before export.
"""

from __future__ import annotations

import re
from typing import Any

from cn_social_agent.cards.build import DANGLING_TAIL_RE, looks_truncated

_SHALLOW_RE = re.compile(
    r"(今天讲一下|简单介绍|众所周知|赋能|干货满满|一文读懂|未来可期|抓住机遇)",
    re.I,
)
_SERP_NOISE_RE = re.compile(
    r'(clamp|isPc|summarySpan|"styles"|pageStyleUpgrade|sc-image|'
    r"OSCHINA\.\.\.|CSDN博客|知乎\s*播报|html>|</?\w+)",
    re.I,
)
_KIND_SET = frozenset({"concept", "keypoints", "steps", "compare", "data", "quote"})


def _flow_item_broken(item: str, points: list[str]) -> bool:
    s = str(item or "").strip()
    if not s:
        return True
    if looks_truncated(s):
        return True
    # Dangling CJK connector — typical mid-phrase cut (…中的 / …与)
    if len(s) >= 6 and DANGLING_TAIL_RE.search(s):
        return True
    return False


def journal_depth_report(
    payload: dict[str, Any] | None,
    *,
    rich_journal: bool = True,
) -> dict[str, Any]:
    """Return pass/fail metrics for a composed journal."""
    doc = payload if isinstance(payload, dict) else {}
    knowledge = [k for k in (doc.get("knowledge") or []) if isinstance(k, dict)]
    cover = doc.get("cover") if isinstance(doc.get("cover"), dict) else {}
    fm = doc.get("frontMatter") if isinstance(doc.get("frontMatter"), dict) else {}
    guide = fm.get("guide") if isinstance(fm.get("guide"), dict) else {}
    toc = fm.get("toc") if isinstance(fm.get("toc"), list) else []
    promises = [p for p in (guide.get("promises") or []) if str(p).strip()]

    kinds = {
        str(k.get("card_kind") or "").strip().lower()
        for k in knowledge
        if str(k.get("card_kind") or "").strip().lower() in _KIND_SET
    }
    with_eid = sum(1 for k in knowledge if k.get("evidenceIds"))
    padded = sum(1 for k in knowledge if k.get("paddedFromTheme"))
    with_diagram = sum(
        1
        for k in knowledge
        if isinstance(k.get("diagram"), dict) and (k["diagram"].get("type") or k["diagram"].get("nodes"))
    )

    flow_broken = 0
    for k in knowledge:
        pts = [str(p) for p in (k.get("realPoints") or []) if str(p).strip()]
        for f in k.get("flow") or []:
            if _flow_item_broken(str(f), pts):
                flow_broken += 1
                break

    tags = cover.get("tags") if isinstance(cover.get("tags"), list) else []
    tags_ok = bool(tags) and not any(looks_truncated(t) for t in tags)
    market = str(cover.get("marketNote") or "")
    market_ok = bool(market.strip()) and not _SERP_NOISE_RE.search(market) and not looks_truncated(market)

    blob = "\n".join(
        [
            str(cover.get("title") or ""),
            str(cover.get("description") or ""),
            market,
            *[str(k.get("concept") or "") for k in knowledge],
            *[str(k.get("topicTitle") or "") for k in knowledge],
        ]
    )
    shallow_hits = _SHALLOW_RE.findall(blob)

    data_ok = True
    for k in knowledge:
        if str(k.get("card_kind") or "").lower() == "data":
            if not str(k.get("metric") or "").strip():
                data_ok = False
                break

    compare_ok = True
    for k in knowledge:
        if str(k.get("card_kind") or "").lower() == "compare":
            if not (str(k.get("compare_left") or "").strip() and str(k.get("compare_right") or "").strip()):
                compare_ok = False
                break

    n = len(knowledge)
    checks: dict[str, bool] = {
        "cards_ge_5": n >= 5 if rich_journal else n >= 3,
        "kinds_ge_3": len(kinds) >= 3 if rich_journal else len(kinds) >= 2,
        "has_front_matter": (len(promises) >= 3 and len(toc) >= min(n, 3)) if rich_journal else True,
        "evidence_coverage_ge_half": n == 0 or with_eid >= max(1, (n + 1) // 2),
        "no_theme_pad": padded == 0,
        "flow_not_truncated": flow_broken == 0,
        "diagrams_complete": n == 0 or with_diagram >= n,
        "cover_tags_ok": tags_ok,
        "market_note_clean": market_ok or not market.strip(),
        "data_has_metric": data_ok,
        "compare_has_sides": compare_ok,
        "no_shallow_cliche": len(shallow_hits) == 0,
        "mode_not_cached": str(doc.get("mode") or "") not in ("cached",),
    }

    failed = [k for k, v in checks.items() if not v]
    return {
        "ok": len(failed) == 0,
        "checks": checks,
        "failed": failed,
        "stats": {
            "cards": n,
            "kinds": sorted(kinds),
            "with_evidence": with_eid,
            "padded": padded,
            "flow_broken": flow_broken,
            "promises": len(promises),
            "toc": len(toc),
            "shallow_hits": shallow_hits[:5],
        },
        "hint": (
            "成刊质检通过"
            if not failed
            else "成刊未达标：" + "、".join(failed[:6])
        ),
    }
