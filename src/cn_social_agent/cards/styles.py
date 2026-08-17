"""YouMind-inspired visual styles + card kinds for knowledge cards."""

from __future__ import annotations

from typing import Any

# Five curated visual styles (YouMind-aligned names)
VISUAL_STYLES: dict[str, dict[str, str]] = {
    "academic": {
        "id": "academic",
        "label": "学术蓝",
        "accent": "#1d4ed8",
        "accent2": "#1e3a8a",
        "ink": "#0f172a",
        "muted": "#475569",
        "paper": "#f8fafc",
        "paper2": "#eef2ff",
        "paper3": "#e0e7ff",
        "soft": "rgba(29,78,216,0.10)",
    },
    "warm": {
        "id": "warm",
        "label": "暖文学",
        "accent": "#9a3412",
        "accent2": "#7c2d12",
        "ink": "#1c1917",
        "muted": "#78716c",
        "paper": "#faf6f1",
        "paper2": "#f3ebe3",
        "paper3": "#e7d9cc",
        "soft": "rgba(154,52,18,0.10)",
    },
    "tech": {
        "id": "tech",
        "label": "暗科技",
        "accent": "#22d3ee",
        "accent2": "#0891b2",
        "ink": "#e2e8f0",
        "muted": "#94a3b8",
        "paper": "#0f172a",
        "paper2": "#111827",
        "paper3": "#1e293b",
        "soft": "rgba(34,211,238,0.12)",
    },
    "magazine": {
        "id": "magazine",
        "label": "杂志红",
        "accent": "#be123c",
        "accent2": "#9f1239",
        "ink": "#1c1917",
        "muted": "#78716c",
        "paper": "#fff7f7",
        "paper2": "#ffe4e6",
        "paper3": "#fecdd3",
        "soft": "rgba(190,18,60,0.10)",
    },
    "mono": {
        "id": "mono",
        "label": "极简黑白",
        "accent": "#171717",
        "accent2": "#404040",
        "ink": "#0a0a0a",
        "muted": "#525252",
        "paper": "#fafafa",
        "paper2": "#f5f5f5",
        "paper3": "#e5e5e5",
        "soft": "rgba(23,23,23,0.08)",
    },
}

# Six card kinds
CARD_KINDS = (
    "quote",
    "keypoints",
    "compare",
    "steps",
    "data",
    "concept",
)

CARD_KIND_LABELS = {
    "quote": "金句",
    "keypoints": "要点",
    "compare": "对比",
    "steps": "步骤",
    "data": "数据",
    "concept": "概念",
}

# Category → default visual style
CATEGORY_DEFAULT_STYLE = {
    "hiring_insight": "academic",
    "product_explain": "tech",
    "skill_roadmap": "warm",
    "industry_brief": "magazine",
}


def resolve_visual_style(style_id: str | None, *, category: str = "") -> dict[str, str]:
    sid = (style_id or "").strip()
    if sid in VISUAL_STYLES:
        return dict(VISUAL_STYLES[sid])
    fallback = CATEGORY_DEFAULT_STYLE.get(category) or "academic"
    return dict(VISUAL_STYLES.get(fallback) or VISUAL_STYLES["academic"])


def infer_card_kind(card: dict[str, Any]) -> str:
    """Heuristic kind from card fields."""
    explicit = str(card.get("card_kind") or card.get("kind") or "").strip().lower()
    if explicit in CARD_KINDS:
        return explicit
    title = str(card.get("topicTitle") or "")
    concept = str(card.get("concept") or "")
    blob = f"{title}\n{concept}\n{card.get('keyPoint') or ''}"
    if any(x in blob for x in ("vs", "对比", "而非", "不是…而是", "误区")):
        return "compare"
    if any(x in blob for x in ("步骤", "流程", "①", "1.", "阶段", "→")):
        return "steps"
    if any(x in blob for x in ("%", "倍", "召回", "Recall", "P95", "指标", "数据")):
        return "data"
    if len(concept) <= 48 and ("「" in concept or "”" in concept or len(concept) < 36):
        if "：" not in concept and len(concept) < 40:
            return "quote"
    if any(x in blob for x in ("定义", "是什么", "概念", "误解")):
        return "concept"
    return "keypoints"


def list_visual_styles() -> list[dict[str, str]]:
    return [{"id": k, "label": v["label"]} for k, v in VISUAL_STYLES.items()]


def list_card_kinds() -> list[dict[str, str]]:
    return [{"id": k, "label": CARD_KIND_LABELS[k]} for k in CARD_KINDS]
