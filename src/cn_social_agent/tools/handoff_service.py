"""Shared hotspot handoff: build payload + create Content Project.

Both the HTTP route (`POST /api/hotspots/handoff`) and the agent tool
(`handoff_hotspot`) must go through here so every handoff lands on the
project board — agent-driven handoffs previously bypassed the hub.
"""

from __future__ import annotations

from typing import Any

from cn_social_agent.tools.hotspot_handoff import build_handoff_payload


async def create_handoff(
    *,
    title: str,
    url: str = "",
    source: str = "",
    why: str = "",
    topic_key: str = "",
    track: str = "koubo",
    research_notes: str = "",
    user_id: str = "",
    email: str = "",
    create_project: bool = True,
) -> dict[str, Any]:
    out = await build_handoff_payload(
        title=title,
        url=url,
        source=source,
        why=why,
        topic_key=topic_key,
        track=track,
        research_notes=research_notes,
    )
    if not out.get("ok") or not create_project:
        return out
    uid = (user_id or "").strip()
    if not uid:
        return out
    try:
        from cn_social_agent.content import service as cps

        topic = str(out.get("short_topic") or out.get("topic") or "").strip()
        proj = await cps.create_project(
            topic=topic,
            user_id=uid,
            email=(email or "").strip(),
            category=str(out.get("category") or "").strip(),
            research_notes=str(out.get("research_notes") or "").strip(),
            search_terms=out.get("search_terms") if isinstance(out.get("search_terms"), list) else None,
            source={
                "kind": "hotspot",
                "url": str(out.get("url") or ""),
                "title": topic,
                "name": str(out.get("source") or ""),
            },
            why=str(out.get("why") or "").strip(),
            topic_key=str(out.get("topic_key") or "").strip(),
            url=str(out.get("url") or "").strip(),
        )
        out["topic_key"] = proj["id"]
        out["short_topic"] = proj.get("short_topic") or topic
    except Exception as exc:  # noqa: BLE001 — handoff still works without project
        out["content_project_error"] = str(exc)[:160]
    return out
