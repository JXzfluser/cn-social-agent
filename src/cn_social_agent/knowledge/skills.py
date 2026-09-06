"""Skill management for Know-How (preset + experience).

Preset skills come from the filesystem ``skills/`` directory via ``SkillLoader``.
Experience skills live in ``wb_topic_skills`` (per-topic, user-authored or
LLM-extracted from workflow records). Both are merged for Agent prompt injection.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional

from cn_social_agent.skills.loader import Skill, SkillLoader


TABLE_SKILLS = "wb_topic_skills"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _row_to_experience_skill(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize a wb_topic_skills row into the API shape."""
    source_workflows = row.get("source_workflows") or []
    if isinstance(source_workflows, str):
        try:
            source_workflows = json.loads(source_workflows) or []
        except (ValueError, json.JSONDecodeError):
            source_workflows = []
    return {
        "id": row.get("id"),
        "topic_key": row.get("topic_key"),
        "skill_name": row.get("skill_name") or "",
        "when_to_use": row.get("when_to_use") or "",
        "body": row.get("body") or "",
        "source_workflows": source_workflows,
        "skill_type": row.get("skill_type") or "experience",
        "enabled": bool(row.get("enabled", True)),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def list_preset_skills(loader: Optional[SkillLoader] = None) -> list[dict[str, Any]]:
    """List filesystem preset skills (read-only, no DB)."""
    if loader is None:
        return []
    out: list[dict[str, Any]] = []
    for s in loader.list_skills():
        out.append(
            {
                "id": s.id,
                "skill_name": s.name,
                "description": s.description,
                "body": s.body,
                "skill_type": "preset_ref",
                "enabled": s.enabled,
                "preset": True,
            }
        )
    return out


async def list_experience_skills(db: Any, *, user_id: str, topic_key: str) -> list[dict[str, Any]]:
    """List experience skills for a topic."""
    if not db or not topic_key:
        return []
    rows = await db.query(
        TABLE_SKILLS,
        filters={"user_id": f"eq.{user_id}", "topic_key": f"eq.{topic_key}"},
        order="updated_at.desc",
        limit=100,
    )
    return [_row_to_experience_skill(r) for r in (rows or [])]


async def create_experience_skill(
    db: Any,
    *,
    user_id: str,
    topic_key: str,
    skill_name: str,
    when_to_use: str = "",
    body: str = "",
    source_workflows: Optional[list[str]] = None,
    skill_type: str = "experience",
    enabled: bool = True,
) -> dict[str, Any]:
    """Insert a new experience skill row."""
    if not db:
        return {"error": "db unavailable"}
    row = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "topic_key": topic_key,
        "skill_name": skill_name or "未命名经验",
        "when_to_use": when_to_use,
        "body": body,
        "source_workflows": json.dumps(source_workflows or []),
        "skill_type": skill_type,
        "enabled": enabled,
    }
    created = await db.create(TABLE_SKILLS, row)
    if created:
        return _row_to_experience_skill(created[0])
    return _row_to_experience_skill(row)


async def patch_experience_skill(
    db: Any,
    *,
    skill_id: str,
    user_id: str,
    updates: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Patch an experience skill (name/when_to_use/body/enabled)."""
    if not db:
        return None
    allowed = {
        "skill_name": "skill_name",
        "when_to_use": "when_to_use",
        "body": "body",
        "skill_type": "skill_type",
        "enabled": "enabled",
        "source_workflows": "source_workflows",
    }
    patch_body = {col: updates[k] for k, col in allowed.items() if k in updates}
    if isinstance(patch_body.get("source_workflows"), (list, dict)):
        patch_body["source_workflows"] = json.dumps(patch_body["source_workflows"])
    if not patch_body:
        return None
    patched = await db.update(
        TABLE_SKILLS, {"id": f"eq.{skill_id}", "user_id": f"eq.{user_id}"}, patch_body
    )
    if not patched:
        return None
    return _row_to_experience_skill(patched[0])


async def delete_experience_skill(db: Any, *, skill_id: str, user_id: str = "") -> bool:
    """Delete an experience skill row."""
    if not db:
        return False
    filters: dict[str, str] = {"id": f"eq.{skill_id}"}
    if user_id:
        filters["user_id"] = f"eq.{user_id}"
    await db.delete(TABLE_SKILLS, filters)
    return True


async def fetch_workflow_records_for_extraction(
    db: Any, *, user_id: str, topic_key: str, min_count: int = 3
) -> list[dict[str, Any]]:
    """Fetch ≥ min_count workflow records for skill extraction. Returns list (may be < min_count)."""
    if not db or not topic_key:
        return []
    rows = await db.query(
        "wb_topic_workflow_records",
        filters={"user_id": f"eq.{user_id}", "topic_key": f"eq.{topic_key}"},
        order="updated_at.desc",
        limit=20,
    )
    return rows or []


def _build_extract_prompt(topic_key: str, workflows: list[dict[str, Any]]) -> str:
    """Build the LLM prompt to abstract when_to_use + body from workflows."""
    parts = [
        "你是经验沉淀助手。根据以下工作流记录，抽象出该话题下复用度最高的经验 skill。",
        "",
        f"话题 key: {topic_key}",
        f"工作流数量: {len(workflows)}",
        "",
        "## 工作流记录",
        "",
    ]
    for i, wf in enumerate(workflows[:8], 1):
        title = wf.get("title") or f"工作流 {i}"
        steps = wf.get("steps") or []
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except (ValueError, json.JSONDecodeError):
                steps = []
        outcome = wf.get("outcome") or ""
        parts.append(f"### {i}. {title}")
        if outcome:
            parts.append(f"outcome: {outcome}")
        if isinstance(steps, list) and steps:
            for j, step in enumerate(steps, 1):
                if isinstance(step, dict):
                    desc = step.get("description") or step.get("action") or step.get("text") or json.dumps(step, ensure_ascii=False)
                else:
                    desc = str(step)
                parts.append(f"{j}. {desc}")
        parts.append("")

    parts.extend(
        [
            "## 要求",
            "- 返回 JSON：{\"skill_name\":\"\",\"when_to_use\":\"\",\"body\":\"\"}",
            "- skill_name：≤16 字，动作型（如 \"选题验证三步法\"）",
            "- when_to_use：≤80 字，描述触发场景",
            "- body：300-500 字，写清步骤与判断要点，可列点",
            "- 不要包含 markdown 代码块包裹",
        ]
    )
    return "\n".join(parts)


async def extract_skills_from_workflows(
    workflows: list[dict[str, Any]],
    *,
    topic_key: str,
    llm_client: Any,
) -> dict[str, Any]:
    """Call LLM to abstract a skill suggestion from workflows. Returns suggestion dict (not persisted)."""
    if len(workflows) < 3:
        return {"error": "至少需要 3 条工作流记录才能提取经验 skill", "workflow_count": len(workflows)}
    prompt = _build_extract_prompt(topic_key, workflows)
    try:
        result = await llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800,
        )
    except Exception as exc:
        return {"error": f"LLM 调用失败：{exc}"}
    text = ""
    if isinstance(result, dict):
        text = result.get("content") or result.get("text") or ""
        if not text and isinstance(result.get("choices"), list):
            msg = result["choices"][0].get("message") if result["choices"] else None
            text = (msg or {}).get("content") or ""
    text = (text or "").strip()
    if text.startswith("```"):
        # strip markdown fences
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        suggestion = json.loads(text)
    except (ValueError, json.JSONDecodeError):
        return {"error": "LLM 输出非 JSON", "raw": text[:1000]}
    if not isinstance(suggestion, dict):
        return {"error": "LLM 输出结构错误", "raw": text[:1000]}
    suggestion["source_workflows"] = [w.get("id") for w in workflows if w.get("id")]
    suggestion["workflow_count"] = len(workflows)
    return suggestion


async def confirm_extracted_skill(
    db: Any,
    *,
    user_id: str,
    topic_key: str,
    suggestion: dict[str, Any],
) -> dict[str, Any]:
    """Persist a confirmed suggestion as a new experience skill."""
    return await create_experience_skill(
        db,
        user_id=user_id,
        topic_key=topic_key,
        skill_name=suggestion.get("skill_name") or "未命名经验",
        when_to_use=suggestion.get("when_to_use") or "",
        body=suggestion.get("body") or "",
        source_workflows=suggestion.get("source_workflows") or [],
        skill_type="experience",
        enabled=True,
    )


def experience_skills_as_prompt_block(skills: list[dict[str, Any]]) -> str:
    """Render experience skills into the same prompt block shape as preset skills."""
    if not skills:
        return ""
    parts = ["# Experience Skills (topic)", ""]
    for s in skills:
        name = s.get("skill_name") or "经验"
        when = s.get("when_to_use") or ""
        body = s.get("body") or ""
        parts.append(f"## {name}")
        if when:
            parts.append(f"when_to_use: {when}")
        parts.append("")
        parts.append(body)
        parts.append("")
    return "\n".join(parts)


def merge_skills_for_prompt(
    preset_skills: list[Skill],
    experience_rows: list[dict[str, Any]],
) -> list[Any]:
    """Return a flat list (Skill + dict) for prompt block assembly."""
    merged: list[Any] = list(preset_skills)
    for r in experience_rows:
        if not r.get("enabled", True):
            continue
        merged.append(
            {
                "id": r.get("id"),
                "name": r.get("skill_name") or "经验",
                "description": r.get("when_to_use") or "",
                "body": r.get("body") or "",
                "preset": False,
            }
        )
    return merged
