"""Loads expert packs from declarative YAML files.

Experts are data, not code: adding a specialist means dropping a YAML file
into ``experts/`` — no Python change, no redeploy of logic. The registry owns
parsing, validation and lookup.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

from .models import Expert, LocalizedText, RubricItem, pick

logger = logging.getLogger(__name__)


def _as_localized(value: Any, fallback: str = "") -> LocalizedText:
    """Accept a plain string (assumed zh-CN) or an explicit locale map."""
    if value is None:
        return {"zh-CN": fallback, "en-US": fallback} if fallback else {}
    if isinstance(value, str):
        return {"zh-CN": value, "en-US": value}
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    return {"zh-CN": str(value), "en-US": str(value)}


class ExpertRegistry:
    """In-memory catalogue of expert packs."""

    def __init__(self, search_dirs: Optional[Iterable[Path]] = None) -> None:
        dirs = list(search_dirs) if search_dirs else default_search_dirs()
        self.search_dirs = dirs
        self._experts: dict[str, Expert] = {}
        self._errors: list[str] = []

    # ── loading ──────────────────────────────────────────────────

    def scan(self) -> "ExpertRegistry":
        self._experts.clear()
        self._errors.clear()
        for directory in self.search_dirs:
            if not directory or not directory.is_dir():
                continue
            for path in sorted(directory.rglob("*.y*ml")):
                try:
                    expert = self._load_file(path)
                except Exception as exc:  # noqa: BLE001
                    msg = f"expert pack {path.name} skipped: {exc}"
                    logger.warning(msg)
                    self._errors.append(msg)
                    continue
                if expert.id in self._experts:
                    logger.warning("duplicate expert id %s (%s), keeping first", expert.id, path)
                    continue
                self._experts[expert.id] = expert
        return self

    @staticmethod
    def _load_file(path: Path) -> Expert:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("expert pack must be a mapping")
        expert_id = str(raw.get("id") or path.stem).strip()
        if not expert_id:
            raise ValueError("missing expert id")

        rubric: list[RubricItem] = []
        for index, item in enumerate(raw.get("rubric") or []):
            if not isinstance(item, dict):
                raise ValueError(f"rubric[{index}] must be a mapping")
            item_id = str(item.get("id") or f"r{index + 1}")
            rubric.append(
                RubricItem(
                    id=item_id,
                    title=_as_localized(item.get("title"), item_id),
                    kind=str(item.get("kind") or "auto"),
                    severity=str(item.get("severity") or "blocker"),
                    rule=str(item.get("rule") or ""),
                    params=dict(item.get("params") or {}),
                    hint=_as_localized(item.get("hint")),
                )
            )

        return Expert(
            id=expert_id,
            name=_as_localized(raw.get("name"), expert_id),
            tagline=_as_localized(raw.get("tagline")),
            persona=str(raw.get("persona") or ""),
            domain=str(raw.get("domain") or "general"),
            capabilities=[str(c) for c in (raw.get("capabilities") or [])],
            runner=str(raw.get("runner") or "llm_brief"),
            rubric=rubric,
            output_kind=str(raw.get("output_kind") or "markdown"),
            enabled=bool(raw.get("enabled", True)),
            tags=[str(t) for t in (raw.get("tags") or [])],
            source=str(path),
            options=dict(raw.get("options") or {}),
        )

    # ── lookup ───────────────────────────────────────────────────

    def all(self, *, include_disabled: bool = False) -> list[Expert]:
        return [
            e for e in self._experts.values() if include_disabled or e.enabled
        ]

    def get(self, expert_id: str) -> Optional[Expert]:
        return self._experts.get(str(expert_id))

    def require(self, expert_id: str) -> Expert:
        expert = self.get(expert_id)
        if expert is None:
            raise KeyError(f"unknown expert: {expert_id}")
        return expert

    def ids(self) -> list[str]:
        return sorted(self._experts)

    @property
    def errors(self) -> list[str]:
        return list(self._errors)

    def __len__(self) -> int:
        return len(self._experts)

    def __contains__(self, expert_id: object) -> bool:
        return str(expert_id) in self._experts

    # ── serialisation ────────────────────────────────────────────

    def as_list(self, locale: str = "zh-CN") -> list[dict[str, Any]]:
        return [e.to_dict(locale) for e in self.all()]

    def summary(self, locale: str = "zh-CN") -> list[dict[str, Any]]:
        rows = []
        for expert in self.all():
            data = expert.to_dict(locale)
            data.pop("persona", None)
            rows.append(data)
        return rows


def default_search_dirs() -> list[Path]:
    """Built-in packs plus the project's own ``experts/`` directory."""
    here = Path(__file__).resolve().parent
    builtin = here / "packs"
    project_root = here.parent.parent.parent
    return [builtin, project_root / "experts"]


def pick_localized(text: Optional[LocalizedText], locale: str) -> str:
    return pick(text, locale)
