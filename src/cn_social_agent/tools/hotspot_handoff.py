"""Shared handoff builder: hotspot item → propose_* payload for a workshop track."""

from __future__ import annotations

from typing import Any

TRACKS = ("koubo", "presentation", "journal")

_NOTES_LIMIT = 2000


async def _research_from_url(url: str) -> str:
    from cn_social_agent.tools.builtin import tool_fetch_url_text

    try:
        fetched = await tool_fetch_url_text(url, max_chars=_NOTES_LIMIT)
    except Exception as exc:  # noqa: BLE001 — handoff must not fail on fetch
        return f"(抓取失败: {str(exc)[:120]})"
    if not isinstance(fetched, dict) or not fetched.get("ok"):
        err = (fetched or {}).get("error") if isinstance(fetched, dict) else ""
        return f"(抓取失败: {str(err or 'unknown')[:120]})"
    text = str(fetched.get("text") or "")
    title = str(fetched.get("title") or "").strip()
    if title and text:
        text = f"{title}\n{text}"
    return text[:_NOTES_LIMIT]


async def build_handoff_payload(
    *,
    title: str,
    url: str = "",
    source: str = "",
    why: str = "",
    topic_key: str = "",
    track: str = "koubo",
    research_notes: str = "",
) -> dict[str, Any]:
    """Build a workshop handoff payload (koubo / presentation / journal).

    Fetches a short excerpt from ``url`` only when ``research_notes`` is empty.
    """
    track_s = (track or "koubo").strip().lower()
    if track_s not in TRACKS:
        return {"ok": False, "error": "track must be koubo|presentation|journal"}
    title_s = (title or "").strip()
    if not title_s:
        return {"ok": False, "error": "title required"}
    url_s = (url or "").strip()
    why_s = (why or "").strip()
    source_s = (source or "").strip()

    notes = (research_notes or "").strip()
    if not notes and url_s:
        notes = await _research_from_url(url_s)
    notes = notes[:_NOTES_LIMIT]

    bundle = "\n".join(
        part
        for part in (
            f"为何值得做：{why_s}" if why_s else "",
            f"来源：{source_s}" if source_s else "",
            f"链接：{url_s}" if url_s else "",
            f"\n{notes}" if notes else "",
        )
        if part
    ).strip()

    base: dict[str, Any] = {
        "ok": True,
        "track": track_s,
        "topic": title_s,
        "topic_key": (topic_key or "").strip(),
        "research_notes": bundle,
        "why": why_s,
        "url": url_s,
        "source": source_s,
    }
    if track_s == "koubo":
        return {
            **base,
            "propose_short_video": True,
            "video_track": "koubo",
            "workshop_mode": "koubo",
            "content_angle": "intro",
            "seconds": 120,
            "hint": "已带调研笔记交接口播轨：在短视频工坊补受众/场景后出 L0 分镜。",
        }
    if track_s == "presentation":
        return {
            **base,
            "propose_presentation": True,
            "presentation": True,
            "auto_draft": True,
            "needs_deep_draft": True,
            "aspect": "9:16",
            "theme": "talent-map",
            "video_track": "presentation",
            "workshop_mode": "presentation",
            "hint": "已带调研笔记交接讲解演示：打开后自动深度起草 thesis / 大纲 / 图示。",
        }
    from cn_social_agent.cards.topic import build_search_terms, extract_short_topic

    short_topic = extract_short_topic(title_s, notes) or title_s
    search_terms = build_search_terms(title_s, notes)
    return {
        **base,
        "propose_cards": True,
        # Search the distilled subject, not the whole long headline.
        "roles": [short_topic],
        "topic": short_topic,
        "short_topic": short_topic,
        "search_terms": search_terms,
        "category": _infer_journal_category(short_topic, why_s, notes, source_s),
        "workshop_mode": "cards",
        "hint": "已带原文素材进知识卡片工坊：默认生成种子证据，不足可「补搜」，勾选后「成刊」。",
    }


def _infer_journal_category(*texts: str) -> str:
    from cn_social_agent.cards.categories import CATEGORIES, infer_category

    cat = infer_category(*texts, default="product_explain")
    return cat if cat in CATEGORIES else "product_explain"
