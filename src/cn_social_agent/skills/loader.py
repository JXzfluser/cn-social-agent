"""SKILL.md loader for the workbench."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Skill:
    id: str
    name: str
    description: str
    body: str
    path: str
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "path": self.path,
            "metadata": self.metadata,
        }


_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    match = _FRONT_MATTER.match(text)
    if not match:
        return {}, text.strip()
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip("\"'")
    return meta, match.group(2).strip()


class SkillLoader:
    def __init__(self, skills_dir: str | Path) -> None:
        self.skills_dir = Path(skills_dir)
        self._skills: dict[str, Skill] = {}

    def scan(self) -> list[Skill]:
        self._skills.clear()
        if not self.skills_dir.exists():
            return []
        for path in sorted(self.skills_dir.rglob("SKILL.md")):
            skill = self.load_file(path)
            if skill:
                self._skills[skill.id] = skill
        return list(self._skills.values())

    def load_file(self, path: str | Path) -> Optional[Skill]:
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_front_matter(text)
        skill_id = meta.get("id") or path.parent.name
        name = meta.get("name") or skill_id
        description = meta.get("description") or body.split("\n", 1)[0][:200]
        return Skill(
            id=skill_id,
            name=name,
            description=description,
            body=body,
            path=str(path),
            metadata=meta,
        )

    def list_skills(self) -> list[dict[str, Any]]:
        if not self._skills:
            self.scan()
        return [s.to_dict() for s in self._skills.values()]

    def get(self, skill_id: str) -> Optional[Skill]:
        if not self._skills:
            self.scan()
        return self._skills.get(skill_id)

    def set_enabled(self, skill_id: str, enabled: bool) -> Optional[Skill]:
        skill = self.get(skill_id)
        if not skill:
            return None
        skill.enabled = enabled
        return skill

    def enabled_prompt_block(self) -> str:
        if not self._skills:
            self.scan()
        return prompt_block_for_skills(
            [s for s in self._skills.values() if s.enabled]
        )

    def select_skills_for_message(self, user_text: str) -> list[Skill]:
        """Pick enabled skills relevant to the latest user message (on-demand)."""
        if not self._skills:
            self.scan()
        enabled = [s for s in self._skills.values() if s.enabled]
        return select_skills_for_message(enabled, user_text)

    def prompt_block_for_message(self, user_text: str) -> str:
        return prompt_block_for_skills(self.select_skills_for_message(user_text))


_URL_RE = re.compile(r"https?://\S+", re.I)

# Triggers: (skill_id, compiled patterns). Order = preference when multiple match.
_SKILL_TRIGGERS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "web-video-presentation",
        (
            re.compile(r"(讲解演示|知识讲解视频|web[- ]?presentation|演示页|Harness.*视频|文章转.*(演示|视频))", re.I),
            re.compile(r"(OBS|\?auto=1|可点击.*演示)", re.I),
        ),
    ),
    (
        "hiring-insight-cards",
        (
            re.compile(
                r"(招聘洞察|雇主品牌|能力图谱|招聘卡片|岗位卡片|JD\b|招(人|聘).{0,8}(卡片|内容))",
                re.I,
            ),
        ),
    ),
    (
        "tech-saas-content",
        (
            re.compile(
                r"(内容操作系统|FDE|技术\s*SaaS|开发者(内容|营销)|产品更新口播|Changelog|周更(内容|短视频)|内容流水线)",
                re.I,
            ),
        ),
    ),
    (
        "short-video-researcher",
        (_URL_RE, re.compile(r"(分析(这个)?链接|这个网站能拍|读一下(这个)?链接)", re.I)),
    ),
    (
        "github-star-growth-video",
        (
            re.compile(r"github\.com/[\w.-]+/[\w.-]+", re.I),
            re.compile(r"(热点|扫榜|star\s*增长|涨星|github)", re.I),
        ),
    ),
    (
        "deep-analysis-video",
        (re.compile(r"(深度分析|规律|证据链|复盘|桌面分析)", re.I),),
    ),
    (
        "short-video-director",
        (re.compile(r"(做片|短视频|口播|分镜|成片|拍一条)", re.I),),
    ),
)


def select_skills_for_message(
    skills: list[Skill],
    user_text: str,
) -> list[Skill]:
    """Select a minimal skill set for the user message.

    Disabled skills must not be passed in (caller filters). Default: inject
    ``short-video-director`` when nothing else matches.
    """
    by_id = {s.id: s for s in skills}
    text = user_text or ""
    picked: list[Skill] = []
    seen: set[str] = set()

    for skill_id, patterns in _SKILL_TRIGGERS:
        skill = by_id.get(skill_id)
        if not skill or skill_id in seen:
            continue
        if any(p.search(text) for p in patterns):
            picked.append(skill)
            seen.add(skill_id)

    if not picked:
        fallback = by_id.get("short-video-director")
        if fallback:
            picked.append(fallback)

    return picked


def prompt_block_for_skills(skills: list[Skill]) -> str:
    if not skills:
        return ""
    parts = ["# Active Skills", ""]
    for skill in skills:
        parts.append(f"## {skill.name} (`{skill.id}`)")
        parts.append(skill.description)
        parts.append("")
        parts.append(skill.body)
        parts.append("")
    return "\n".join(parts)
