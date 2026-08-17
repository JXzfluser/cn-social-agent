"""Orchestrate Content Project dual-write (local + InsForge)."""

from __future__ import annotations

from typing import Any, Optional

from cn_social_agent.content import cloud as cloud_mod
from cn_social_agent.content.models import normalize_project
from cn_social_agent.content import store_local as local


async def upsert_project(
    rec: dict[str, Any],
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> dict[str, Any]:
    saved = local.save_project(rec, user_id=user_id, email=email)
    ok = False
    try:
        ok = await cloud_mod.upsert_content_record(saved, user_id=user_id, email=email)
    except Exception:  # noqa: BLE001
        ok = False
    out = dict(saved)
    out["persisted"] = "insforge" if ok else "local"
    return out


async def create_project(
    *,
    topic: str,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    category: str = "",
    research_notes: str = "",
    search_terms: Optional[list[Any]] = None,
    source: Optional[dict[str, Any]] = None,
    why: str = "",
    topic_key: str = "",
    url: str = "",
) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "topic": topic,
        "category": category,
        "research_notes": research_notes,
        "why": why,
        "topic_key": topic_key,
        "url": url,
    }
    if search_terms:
        raw["search_terms"] = search_terms
    if source:
        raw["source"] = source
    return await upsert_project(raw, user_id=user_id, email=email)


async def get_project(
    project_id: str,
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    got = None
    try:
        got = await cloud_mod.get_content_record(project_id, user_id=user_id, email=email)
    except Exception:  # noqa: BLE001
        got = None
    if got:
        # Keep local in sync
        local.save_project(got, user_id=user_id, email=email)
        return got
    return local.get_project(project_id, user_id=user_id, email=email)


async def list_projects(
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    limit: int = 40,
) -> list[dict[str, Any]]:
    cloud_rows: list[dict[str, Any]] = []
    try:
        cloud_rows = await cloud_mod.list_content_records(
            user_id=user_id, email=email, limit=limit
        )
    except Exception:  # noqa: BLE001
        cloud_rows = []
    local_rows = local.list_projects(user_id=user_id, email=email, limit=limit)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in cloud_rows + local_rows:
        pid = str(r.get("id") or "")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        out.append(normalize_project(r, user_id=user_id, email=email))
    out.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    return out[: max(1, min(100, int(limit or 40)))]


async def patch_project(
    project_id: str,
    patch: dict[str, Any],
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    cur = await get_project(project_id, user_id=user_id, email=email)
    if not cur:
        return None
    merged = dict(cur)
    for key in (
        "topic",
        "short_topic",
        "category",
        "research_notes",
        "search_terms",
        "status",
        "why",
        "topic_key",
        "quality",
    ):
        if key in patch and patch[key] is not None:
            merged[key] = patch[key]
    if "evidence_pack" in patch and isinstance(patch["evidence_pack"], dict):
        merged["evidence_pack"] = patch["evidence_pack"]
    elif "evidencePack" in patch and isinstance(patch["evidencePack"], dict):
        merged["evidence_pack"] = patch["evidencePack"]
    if "source" in patch and isinstance(patch["source"], dict):
        merged["source"] = {**(merged.get("source") or {}), **patch["source"]}
    if "artifacts" in patch and isinstance(patch["artifacts"], dict):
        merged["artifacts"] = {**(merged.get("artifacts") or {}), **patch["artifacts"]}
    if "canvas" in patch and isinstance(patch["canvas"], dict):
        merged["canvas"] = patch["canvas"]
    return await upsert_project(merged, user_id=user_id, email=email)


async def attach_artifacts(
    project_id: str,
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    journal_id: Optional[str] = None,
    video_id: Optional[str] = None,
    presentation_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    arts: dict[str, Any] = {}
    if journal_id is not None:
        arts["journal_id"] = journal_id or None
    if video_id is not None:
        arts["video_id"] = video_id or None
    if presentation_id is not None:
        arts["presentation_id"] = presentation_id or None
    if not arts:
        return await get_project(project_id, user_id=user_id, email=email)
    return await patch_project(
        project_id, {"artifacts": arts}, user_id=user_id, email=email
    )
