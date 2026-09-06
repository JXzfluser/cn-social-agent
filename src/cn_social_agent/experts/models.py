"""Domain model for experts and their acceptance rubrics.

An **expert** is a reusable, declarative unit of work:

* a persona and capability set (what it is good at),
* a runner (which executor performs the work),
* a **rubric** — the acceptance criteria a deliverable must satisfy.

The rubric is what makes "expert tasks can be accepted" a mechanical property
rather than a matter of taste. Each item is either machine-checkable
(``kind="auto"``, evaluated by a gate in :mod:`cn_social_agent.tasks.gates`) or
requires a person (``kind="human"``). Items marked ``severity="blocker"`` stop
the task from ever reaching *completed* until they pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from cn_social_agent.core.tenant import DEFAULT_LOCALE, normalize_locale

# Locale-keyed text: {"zh-CN": "…", "en-US": "…"}
LocalizedText = dict[str, str]

VALID_KINDS = ("auto", "human")
VALID_SEVERITIES = ("blocker", "major", "minor")


def pick(text: Optional[LocalizedText], locale: str = DEFAULT_LOCALE) -> str:
    """Resolve a localized string, degrading gracefully."""
    if not text:
        return ""
    if not isinstance(text, dict):
        return str(text)
    effective = normalize_locale(locale)
    if effective in text:
        return text[effective]
    fallback = DEFAULT_LOCALE if effective != DEFAULT_LOCALE else "en-US"
    for candidate in (fallback, effective.split("-")[0]):
        for key, value in text.items():
            if key.lower() == candidate.lower() or key.lower().startswith(candidate.lower()):
                return value
    return next(iter(text.values()), "")


@dataclass
class RubricItem:
    """A single acceptance criterion."""

    id: str
    title: LocalizedText
    kind: str = "auto"  # auto | human
    severity: str = "blocker"  # blocker | major | minor
    rule: str = ""  # gate name for kind=auto
    params: dict[str, Any] = field(default_factory=dict)
    hint: LocalizedText = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in VALID_KINDS:
            raise ValueError(f"rubric {self.id}: bad kind {self.kind!r}")
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(f"rubric {self.id}: bad severity {self.severity!r}")
        if self.kind == "auto" and not self.rule:
            raise ValueError(f"rubric {self.id}: auto items require a rule")

    @property
    def is_blocker(self) -> bool:
        return self.severity == "blocker"

    @property
    def needs_human(self) -> bool:
        return self.kind == "human"

    def to_dict(self, locale: str = DEFAULT_LOCALE) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": pick(self.title, locale),
            "kind": self.kind,
            "severity": self.severity,
            "rule": self.rule,
            "hint": pick(self.hint, locale) if self.hint else "",
        }


@dataclass
class Expert:
    """A dispatchable specialist."""

    id: str
    name: LocalizedText
    tagline: LocalizedText = field(default_factory=dict)
    persona: str = ""
    domain: str = "general"
    capabilities: list[str] = field(default_factory=list)
    runner: str = "llm_brief"  # executor registered in tasks.runners
    rubric: list[RubricItem] = field(default_factory=list)
    output_kind: str = "markdown"  # markdown | json | video | images
    enabled: bool = True
    tags: list[str] = field(default_factory=list)
    source: str = ""

    # Runtime options handed to the runner.
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, locale: str = DEFAULT_LOCALE) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": pick(self.name, locale),
            "tagline": pick(self.tagline, locale),
            "domain": self.domain,
            "persona": self.persona,
            "capabilities": list(self.capabilities),
            "runner": self.runner,
            "output_kind": self.output_kind,
            "tags": list(self.tags),
            "rubric": [item.to_dict(locale) for item in self.rubric],
            "blockers": sum(1 for item in self.rubric if item.is_blocker),
        }

    def rubric_item(self, item_id: str) -> Optional[RubricItem]:
        for item in self.rubric:
            if item.id == item_id:
                return item
        return None
