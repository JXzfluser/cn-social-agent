"""Content pack loader — vertical skills + templates + defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass
class ContentPack:
    id: str
    path: str
    version: str = "0.1.0"
    customer_profile: str = ""
    skills_enabled: list[str] = field(default_factory=list)
    skills_optional: list[str] = field(default_factory=list)
    templates: list[dict[str, Any]] = field(default_factory=list)
    defaults: dict[str, Any] = field(default_factory=dict)
    cost_estimates_cny: dict[str, float] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "version": self.version,
            "customer_profile": self.customer_profile,
            "skills_enabled": list(self.skills_enabled),
            "skills_optional": list(self.skills_optional),
            "templates": list(self.templates),
            "defaults": dict(self.defaults),
            "cost_estimates_cny": dict(self.cost_estimates_cny),
        }


_active: Optional[ContentPack] = None


def get_active_pack() -> Optional[ContentPack]:
    return _active


def set_active_pack(pack: Optional[ContentPack]) -> None:
    global _active
    _active = pack


def packs_dir() -> Path:
    raw = (os.getenv("PACKS_DIR") or "").strip()
    if raw:
        return Path(raw)
    return _project_root() / "packs"


def _customer_pack_path() -> Optional[Path]:
    explicit = (os.getenv("WORKBENCH_PACK_FILE") or "").strip()
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    customer = (os.getenv("USAGE_CUSTOMER_ID") or os.getenv("WORKBENCH_CUSTOMER") or "").strip()
    if not customer:
        return None
    p = _project_root() / "data" / "customers" / customer / "pack.yaml"
    return p if p.is_file() else None


def resolve_pack_yaml(pack_id: str) -> Optional[Path]:
    """Locate pack.yaml for an id (customer override → packs/ → legacy skills/)."""
    customer = _customer_pack_path()
    if customer is not None:
        return customer

    pid = (pack_id or "").strip()
    if not pid:
        return None

    candidates = [
        packs_dir() / pid / "pack.yaml",
        _project_root() / "skills" / pid / "pack.yaml",
        _project_root() / "skills" / f"{pid}-content" / "pack.yaml",
        _project_root() / "skills" / "tech-saas-content" / "pack.yaml"
        if pid in ("tech-saas", "tech_saas")
        else None,
    ]
    for path in candidates:
        if path is not None and path.is_file():
            return path
    return None


def _normalize_template(entry: Any) -> Optional[dict[str, Any]]:
    if isinstance(entry, str):
        tid = entry.strip()
        if not tid:
            return None
        return {"id": tid, "ref": True}
    if not isinstance(entry, dict):
        return None
    tid = str(entry.get("id") or "").strip()
    if not tid:
        return None
    out = dict(entry)
    out["id"] = tid
    out["ref"] = False
    return out


def load_pack_file(path: Path, *, pack_id: str = "") -> ContentPack:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        data = {}
    pid = (
        str(data.get("id") or pack_id or path.parent.name or "default").strip()
        or "default"
    )
    templates_raw = data.get("templates") or []
    templates: list[dict[str, Any]] = []
    if isinstance(templates_raw, list):
        for item in templates_raw:
            norm = _normalize_template(item)
            if norm:
                templates.append(norm)

    skills_enabled = [
        str(x).strip()
        for x in (data.get("skills_enabled") or [])
        if str(x).strip()
    ]
    skills_optional = [
        str(x).strip()
        for x in (data.get("skills_optional") or [])
        if str(x).strip()
    ]
    costs_raw = data.get("cost_estimates_cny") or {}
    costs: dict[str, float] = {}
    if isinstance(costs_raw, dict):
        for k, v in costs_raw.items():
            try:
                costs[str(k)] = float(v)
            except (TypeError, ValueError):
                continue

    return ContentPack(
        id=pid,
        path=str(path.resolve()),
        version=str(data.get("version") or "0.1.0"),
        customer_profile=str(
            data.get("customer_profile") or data.get("profile") or ""
        ),
        skills_enabled=skills_enabled,
        skills_optional=skills_optional,
        templates=templates,
        defaults=dict(data.get("defaults") or {})
        if isinstance(data.get("defaults"), dict)
        else {},
        cost_estimates_cny=costs,
        raw=data,
    )


def load_pack(pack_id: Optional[str] = None) -> Optional[ContentPack]:
    pid = (pack_id or os.getenv("WORKBENCH_PACK") or "tech-saas").strip()
    if pid.lower() in ("", "none", "off", "0"):
        return None
    path = resolve_pack_yaml(pid)
    if path is None:
        return None
    return load_pack_file(path, pack_id=pid)


def apply_pack_skills(skills: Any, pack: ContentPack) -> None:
    """Set skill.enabled from pack allow-list (before user bindings)."""
    if not pack.skills_enabled:
        return
    allowed = set(pack.skills_enabled) | set(pack.skills_optional)
    # Always keep director if present — golden path safety
    allowed.add("short-video-director")
    if not getattr(skills, "_skills", None):
        skills.scan()
    for skill in skills._skills.values():
        if skill.id in pack.skills_enabled:
            skill.enabled = True
        elif skill.id in pack.skills_optional:
            # optional: leave as currently enabled (default True from loader)
            continue
        elif skill.id in allowed:
            skill.enabled = True
        else:
            skill.enabled = False


def effective_templates(builtin: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Merge builtin VIDEO_TEMPLATES with active pack template defs."""
    out = {k: dict(v) for k, v in builtin.items()}
    pack = get_active_pack()
    if not pack or not pack.templates:
        return out
    for entry in pack.templates:
        tid = entry.get("id") or ""
        if not tid:
            continue
        if entry.get("ref"):
            # Keep builtin; optionally overlay pack defaults.video onto it later
            if tid not in out and tid in builtin:
                out[tid] = dict(builtin[tid])
            continue
        base = dict(out.get(tid) or builtin.get(tid) or {"id": tid})
        for key in (
            "label",
            "hint",
            "content_angle",
            "target_seconds",
            "bg_theme",
            "motion",
            "roles",
            "placeholder_topic",
        ):
            if key in entry and entry[key] is not None:
                base[key] = entry[key]
        base["id"] = tid
        out[tid] = base
    return out


def pack_video_defaults() -> dict[str, Any]:
    pack = get_active_pack()
    if not pack:
        return {}
    video = pack.defaults.get("video") if isinstance(pack.defaults, dict) else {}
    return dict(video) if isinstance(video, dict) else {}


def activate_pack(pack_id: Optional[str] = None) -> Optional[ContentPack]:
    """Load pack, set as active, return it (or None)."""
    pack = load_pack(pack_id)
    set_active_pack(pack)
    return pack
