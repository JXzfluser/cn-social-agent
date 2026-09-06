"""Cross-feature research linking: Content Project ↔ video pipeline.

P1-2 (koubo scripts consume research notes) and P1-4 (video completion
writes back into the Content Project) share the project lookup here so
both directions use the same matching rules.
"""

from __future__ import annotations

from typing import Any, Optional

from cn_social_agent.knowledge.topic_key import topic_key as derive_topic_key


async def find_project(
    *,
    user_id: str,
    email: str = "",
    topic_key: str = "",
    topic: str = "",
) -> Optional[dict[str, Any]]:
    """Locate a Content Project by explicit id, else by topic_key match."""
    from cn_social_agent.content import service as cps

    uid = (user_id or "").strip()
    if not uid:
        return None
    em = (email or "").strip()
    pid = (topic_key or "").strip()
    if pid:
        try:
            proj = await cps.get_project(pid, user_id=uid, email=em)
        except Exception:  # noqa: BLE001
            proj = None
        if isinstance(proj, dict):
            return proj
    key = derive_topic_key(topic or "")
    if not key:
        return None
    try:
        projects = await cps.list_projects(user_id=uid, email=em, limit=100)
    except Exception:  # noqa: BLE001
        return None
    for proj in projects:
        stored = str(proj.get("topic_key") or "").strip()
        if stored == key:
            return proj
        # Projects may not carry a stored key — derive from topic/short_topic
        if not stored and any(
            derive_topic_key(str(proj.get(f) or "")) == key
            for f in ("topic", "short_topic")
        ):
            return proj
    return None


def project_research_notes(proj: dict[str, Any], *, limit: int = 12) -> str:
    """Content Project research_notes + evidence pack → prompt-ready notes."""
    if not isinstance(proj, dict):
        return ""
    parts: list[str] = []
    notes = str(proj.get("research_notes") or "").strip()
    if notes:
        parts.append("项目调研笔记：\n" + notes[:2000])
    pack = proj.get("evidence_pack") or proj.get("evidencePack")
    if isinstance(pack, dict):
        from cn_social_agent.knowledge.assets import format_evidence_pack_notes

        evidence = format_evidence_pack_notes(pack, limit=limit, header="项目证据包（必须吸收）")
        if evidence:
            parts.append(evidence)
    return "\n\n".join(parts)


async def resolve_video_research_notes(
    *,
    user_id: str,
    email: str = "",
    topic: str = "",
    topic_key: str = "",
) -> str:
    """Best-effort research notes for a koubo script.

    Content Project (by id or topic_key) first; falls back to journal
    evidence by topic match (the same path the presentation track uses).
    """
    uid = (user_id or "").strip()
    if not uid:
        return ""
    proj = await find_project(
        user_id=uid,
        email=email,
        topic_key=topic_key,
        topic=topic,
    )
    if proj is not None:
        notes = project_research_notes(proj)
        if notes:
            return notes
    try:
        from cn_social_agent.knowledge.assets import resolve_pack_research_notes

        out = await resolve_pack_research_notes(
            topic=topic, user_id=uid, email=email
        )
        return str(out.get("notes") or "")
    except Exception:  # noqa: BLE001 — research notes are best-effort
        return ""


async def attach_video_artifact(
    *,
    user_id: str,
    email: str = "",
    topic: str = "",
    topic_key: str = "",
    video_id: str,
    quality_pass: Optional[bool] = None,
) -> Optional[dict[str, Any]]:
    """Write a finished video back into its Content Project (P1-4).

    Attaches video_id; when the quality gate passed and the project is
    still `active`, promotes status to `export_ready`.
    """
    proj = await find_project(
        user_id=user_id,
        email=email,
        topic_key=topic_key,
        topic=topic,
    )
    if proj is None:
        return None
    from cn_social_agent.content import service as cps

    patched = await cps.attach_artifacts(
        str(proj.get("id")),
        user_id=user_id,
        email=email,
        video_id=video_id,
    )
    if patched is not None and quality_pass is True:
        status = str(patched.get("status") or "")
        if status in ("", "active", "candidate", "producing"):
            patched = (
                await cps.patch_project(
                    str(proj.get("id")),
                    {"status": "export_ready"},
                    user_id=user_id,
                    email=email,
                )
                or patched
            )
    return patched
