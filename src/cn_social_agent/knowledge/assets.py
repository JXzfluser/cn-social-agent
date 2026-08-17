"""Aggregate journals + video projects into topic assets (read-only)."""

from __future__ import annotations

from typing import Any, Optional

from cn_social_agent.knowledge.topic_key import (
    best_topic_label,
    display_topic,
    primary_topic_key,
    topic_key,
    topics_from_card_record,
)
from cn_social_agent.video.pipeline import decode_script_bundle
from cn_social_agent.video.presentation import is_presentation

ANGLE_LABELS = {
    "intro": "入门讲解",
    "compare": "对比选型",
    "deep_analysis": "深度分析",
    "idea": "观点短评",
    "general": "通用",
}


def _evidence_count(row: dict[str, Any]) -> int:
    pack = row.get("evidencePack") or row.get("evidence_pack") or {}
    if isinstance(pack, dict):
        if isinstance(pack.get("count"), int):
            return int(pack["count"])
        ev = pack.get("evidences")
        if isinstance(ev, list):
            return len(ev)
    return int(row.get("snippetCount") or 0)


def journal_item_from_row(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not isinstance(row, dict):
        return None
    rid = str(row.get("id") or "").strip()
    if not rid:
        return None
    cands = topics_from_card_record(row)
    key = primary_topic_key(cands)
    if not key:
        return None
    label = best_topic_label(cands) or key
    cover = row.get("cover") if isinstance(row.get("cover"), dict) else {}
    return {
        "kind": "journal",
        "id": rid,
        "pack_id": rid,
        "topic_key": key,
        "topic": label,
        "title": str(cover.get("title") or row.get("title") or label)[:80],
        "category": str(row.get("category") or "").strip(),
        "mode": str(row.get("mode") or "").strip(),
        "ts": str(row.get("ts") or ""),
        "evidence_count": _evidence_count(row),
        "edition": str(
            (cover.get("edition") if cover else "") or row.get("edition") or ""
        ),
    }


def video_item_from_row(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not isinstance(row, dict):
        return None
    pid = str(row.get("id") or "").strip()
    if not pid:
        return None
    topic = str(row.get("topic") or "").strip()
    title = str(row.get("title") or "").strip()
    plain, meta = decode_script_bundle(row.get("script") or "")
    if not topic and meta.get("cover_hook"):
        topic = str(meta.get("cover_hook") or "").strip()
    key = topic_key(topic) or topic_key(title)
    if not key:
        return None
    track = "presentation" if is_presentation(row, meta) else "koubo"
    angle = str(meta.get("content_angle") or "").strip()
    return {
        "kind": "video",
        "id": pid,
        "topic_key": key,
        "topic": topic or title or key,
        "title": (title or topic)[:80],
        "track": track,
        "status": str(row.get("status") or "").strip(),
        "content_angle": angle,
        "content_angle_label": ANGLE_LABELS.get(angle, angle),
        "ts": str(row.get("updated_at") or row.get("created_at") or ""),
        "has_output": bool(row.get("output_path")),
        "delivery_level": str(meta.get("delivery_level") or "").strip(),
        "storyboard_confirmed": bool(meta.get("storyboard_confirmed")),
        "script_preview": (plain or "")[:80],
    }


def group_topic_assets(
    *,
    journals: list[dict[str, Any]],
    videos: list[dict[str, Any]],
    recent_topics: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Build topic asset summaries sorted by latest activity."""
    buckets: dict[str, dict[str, Any]] = {}

    def ensure(key: str, label: str) -> dict[str, Any]:
        if key not in buckets:
            buckets[key] = {
                "topic_key": key,
                "topic": label,
                "journals": [],
                "videos": [],
                "journal_count": 0,
                "video_count": 0,
                "evidence_count": 0,
                "latest_ts": "",
            }
        elif label and len(label) < len(str(buckets[key].get("topic") or label)):
            buckets[key]["topic"] = label
        return buckets[key]

    for row in journals:
        item = journal_item_from_row(row)
        if not item:
            continue
        b = ensure(item["topic_key"], item["topic"])
        b["journals"].append(item)
        b["journal_count"] += 1
        b["evidence_count"] = max(b["evidence_count"], int(item.get("evidence_count") or 0))
        ts = str(item.get("ts") or "")
        if ts > str(b.get("latest_ts") or ""):
            b["latest_ts"] = ts

    for row in videos:
        item = video_item_from_row(row)
        if not item:
            continue
        b = ensure(item["topic_key"], item["topic"])
        b["videos"].append(item)
        b["video_count"] += 1
        ts = str(item.get("ts") or "")
        if ts > str(b.get("latest_ts") or ""):
            b["latest_ts"] = ts

    # Seed empty shells from recent prefs so empty topics still show up
    for raw in recent_topics or []:
        key = topic_key(raw)
        if key and key not in buckets:
            ensure(key, best_topic_label([raw]) or key)

    topics = list(buckets.values())
    for t in topics:
        t["journals"].sort(key=lambda x: str(x.get("ts") or ""), reverse=True)
        t["videos"].sort(key=lambda x: str(x.get("ts") or ""), reverse=True)
        t["kinds"] = []
        if t["journal_count"]:
            t["kinds"].append("journal")
        if any(v.get("track") == "koubo" for v in t["videos"]):
            t["kinds"].append("koubo")
        if any(v.get("track") == "presentation" for v in t["videos"]):
            t["kinds"].append("presentation")
    topics.sort(key=lambda x: str(x.get("latest_ts") or ""), reverse=True)
    return topics


def get_topic_asset(topics: list[dict[str, Any]], key: str) -> Optional[dict[str, Any]]:
    want = topic_key(key) or (key or "").strip().lower()
    if not want:
        return None
    for t in topics:
        if t.get("topic_key") == want:
            return t
    return None


def match_topic_assets(
    topics: list[dict[str, Any]],
    query: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Rank topic assets by exact key, then substring overlap with query."""
    q = topic_key(query) or display_topic(query).lower()
    if not q:
        # No query → latest topics with real content
        return [
            t
            for t in topics
            if (t.get("journal_count") or 0) + (t.get("video_count") or 0) > 0
        ][:limit]

    scored: list[tuple[int, str, dict[str, Any]]] = []
    for t in topics:
        key = str(t.get("topic_key") or "")
        label = str(t.get("topic") or "").lower()
        if not key and not label:
            continue
        score = 0
        if key == q:
            score = 100
        elif q in key or key in q:
            score = 80
        elif q in label or label in q:
            score = 60
        else:
            qt = set(q.split())
            kt = set(key.split())
            if qt and kt and qt & kt:
                score = 40 + 10 * len(qt & kt)
        if score <= 0:
            continue
        if (t.get("journal_count") or 0) + (t.get("video_count") or 0) > 0:
            score += 5
        scored.append((score, str(t.get("latest_ts") or ""), t))
    scored.sort(key=lambda x: x[1], reverse=True)
    scored.sort(key=lambda x: x[0], reverse=True)
    return [t for _, _, t in scored[:limit]]


def summarize_asset_hit(t: dict[str, Any]) -> dict[str, Any]:
    """Compact hit for tool / propose enrichment."""
    journals = t.get("journals") or []
    videos = t.get("videos") or []
    return {
        "topic_key": t.get("topic_key"),
        "topic": t.get("topic"),
        "journal_count": t.get("journal_count") or 0,
        "video_count": t.get("video_count") or 0,
        "evidence_count": t.get("evidence_count") or 0,
        "kinds": t.get("kinds") or [],
        "latest_journal_id": journals[0]["id"] if journals else None,
        "latest_pack_id": journals[0].get("pack_id") if journals else None,
        "latest_video_id": videos[0]["id"] if videos else None,
        "latest_ts": t.get("latest_ts") or "",
    }


async def load_journals_for_user(*, user_id: str, email: str = "") -> list[dict[str, Any]]:
    from cn_social_agent.cards.history import load_history

    rows = list(load_history(user_id=user_id, email=email) or [])
    try:
        from cn_social_agent.cards.cloud import list_card_records

        cloud = await list_card_records(user_id=user_id, email=email)
        if cloud:
            seen = {str(r.get("id") or "") for r in cloud if isinstance(r, dict)}
            for r in rows:
                rid = str(r.get("id") or "")
                if rid and rid not in seen:
                    cloud.append(r)
            rows = cloud
    except Exception:  # noqa: BLE001
        pass
    return [r for r in rows if isinstance(r, dict)]


async def load_videos_for_user(
    *,
    user_id: str,
    store_mode: str = "",
    insforge_db: Any = None,
) -> list[dict[str, Any]]:
    if store_mode != "insforge" or insforge_db is None:
        return []
    try:
        from cn_social_agent.video.store import VideoStore

        return list(await VideoStore(insforge_db).list_projects(user_id) or [])
    except Exception:  # noqa: BLE001
        return []


async def gather_topic_assets_for_user(
    *,
    user_id: str,
    email: str = "",
    store_mode: str = "",
    insforge_db: Any = None,
    recent_topics: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    journals = await load_journals_for_user(user_id=user_id, email=email)
    videos = await load_videos_for_user(
        user_id=user_id, store_mode=store_mode, insforge_db=insforge_db
    )
    return group_topic_assets(
        journals=journals, videos=videos, recent_topics=recent_topics or []
    )


async def lookup_local_assets(
    query: str = "",
    *,
    limit: int = 5,
) -> dict[str, Any]:
    """Tool/middleware helper: match local topic assets for current tool user."""
    from cn_social_agent.tools.context import get_tool_context

    ctx = get_tool_context()
    user_id = str(ctx.get("user_id") or "").strip()
    if not user_id:
        return {
            "ok": False,
            "hits": [],
            "hint": "无用户上下文，无法查本地主题资产",
        }
    email = str(ctx.get("email") or "").strip()
    prefs = ctx.get("prefs") if isinstance(ctx.get("prefs"), dict) else {}
    recent = list((prefs or {}).get("recent_topics") or [])
    topics = await gather_topic_assets_for_user(
        user_id=user_id,
        email=email,
        store_mode=str(ctx.get("store_mode") or ""),
        insforge_db=ctx.get("insforge_db"),
        recent_topics=recent,
    )
    matched = match_topic_assets(topics, query, limit=limit)
    hits = [summarize_asset_hit(t) for t in matched]
    # Drop empty shells from lookup (keep them only in full assets UI)
    hits = [
        h
        for h in hits
        if (h.get("journal_count") or 0) + (h.get("video_count") or 0) > 0
    ]
    if hits:
        hint = (
            f"本地已有 {len(hits)} 个相关主题资产；"
            "可先打开主题资产复用证据/成片，再决定是否深采或重做。"
        )
    else:
        hint = "本地暂无相关主题资产，可以深采或新建短视频。"
    return {
        "ok": True,
        "query": (query or "").strip(),
        "hits": hits,
        "total_topics": len(topics),
        "hint": hint,
        "present_topic_assets": True,
    }


def format_evidence_pack_notes(
    pack: dict[str, Any] | None,
    *,
    limit: int = 12,
    header: str = "本地证据包（必须吸收）",
) -> str:
    """Turn a journal evidencePack into research_notes lines for presentation draft."""
    from cn_social_agent.cards.evidence import selected_evidences

    if not isinstance(pack, dict):
        return ""
    selected = selected_evidences(pack)
    if not selected:
        return ""
    ranked = sorted(
        selected,
        key=lambda e: float(e.get("score") or 0),
        reverse=True,
    )[: max(1, limit)]
    lines = [header + "："]
    for i, e in enumerate(ranked, 1):
        text = str(e.get("text") or "").strip().replace("\n", " ")
        if not text:
            continue
        if len(text) > 220:
            text = text[:219].rstrip("，。、；;,. ") + "…"
        src = str(e.get("source") or e.get("url") or e.get("title") or "").strip()
        eid = str(e.get("id") or f"e{i}")
        if src:
            lines.append(f"{i}. [{eid}] {text}（来源感：{src[:60]}）")
        else:
            lines.append(f"{i}. [{eid}] {text}")
    return "\n".join(lines) if len(lines) > 1 else ""


async def resolve_pack_research_notes(
    *,
    pack_id: str = "",
    topic: str = "",
    user_id: str = "",
    email: str = "",
    limit: int = 12,
) -> dict[str, Any]:
    """Load journal evidence by pack_id or best topic match → research_notes snippet."""
    from cn_social_agent.cards.cloud import get_card_record
    from cn_social_agent.cards.history import get_history_item

    pid = (pack_id or "").strip()
    topic_s = (topic or "").strip()
    uid = (user_id or "").strip()
    em = (email or "").strip()
    row: dict[str, Any] | None = None
    source = ""

    if pid and uid:
        row = get_history_item(pid, user_id=uid, email=em or None)
        if row is None:
            try:
                row = await get_card_record(pid, user_id=uid, email=em)
            except Exception:  # noqa: BLE001
                row = None
        if row:
            source = "pack_id"

    if row is None and topic_s and uid:
        topics = await gather_topic_assets_for_user(user_id=uid, email=em)
        matched = match_topic_assets(topics, topic_s, limit=1)
        if matched:
            journals = matched[0].get("journals") or []
            jid = str((journals[0] or {}).get("id") or "").strip() if journals else ""
            if jid:
                row = get_history_item(jid, user_id=uid, email=em or None)
                if row is None:
                    try:
                        row = await get_card_record(jid, user_id=uid, email=em)
                    except Exception:  # noqa: BLE001
                        row = None
                if row:
                    source = "topic_match"
                    pid = jid

    if not isinstance(row, dict):
        return {"ok": False, "notes": "", "pack_id": pid, "source": "", "count": 0}

    pack = row.get("evidencePack") or row.get("evidence_pack") or {}
    cover = row.get("cover") if isinstance(row.get("cover"), dict) else {}
    title = str(cover.get("title") or row.get("title") or topic_s or pid)[:60]
    notes = format_evidence_pack_notes(
        pack if isinstance(pack, dict) else None,
        limit=limit,
        header=f"本地证据包《{title}》",
    )
    from cn_social_agent.cards.evidence import selected_evidences

    count = len(selected_evidences(pack if isinstance(pack, dict) else None))
    return {
        "ok": bool(notes),
        "notes": notes,
        "pack_id": pid or str(row.get("id") or ""),
        "source": source,
        "count": count,
        "title": title,
    }
