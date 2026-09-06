"""Local side-store for preference keys the cloud table has no column for.

`wb_user_prefs` only carries a fixed column set (audience / voice / angle /
platform / recent_topics / llm_mode / llm_model). Everything else — connector
switches, automation state, the scratch canvas — would silently vanish on
save. Keep those keys in a per-user JSON file next to the other local stores.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

EXTRA_KEYS: tuple[str, ...] = (
    "default_video_track",
    "default_pres_aspect",
    "default_pres_theme",
    "recent_recipes",
    "llm_route",
    "llm_model_fast",
    "llm_model_strong",
    "connectors_enabled",
    "hotspot_sources_enabled",
    "automations_enabled",
    "automation_last_run",
    "automation_runs",
    "canvas_scratch",
    "custom_templates",
    "im_webhook",
)


def _safe_key(raw: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_@.+-]+", "_", (raw or "").strip().lower())[:96]
    return s or "anon"


def prefs_dir() -> Path:
    override = (os.getenv("USER_PREFS_DIR") or "").strip()
    if override:
        d = Path(override)
    else:
        root = Path(__file__).resolve().parents[3]
        d = root / "data" / "user_prefs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def prefs_path(user_id: Optional[str]) -> Path:
    return prefs_dir() / f"{_safe_key(user_id or 'anon')}.json"


def read_extras(user_id: Optional[str]) -> dict[str, Any]:
    path = prefs_path(user_id)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if k in EXTRA_KEYS}


def write_extras(user_id: Optional[str], prefs: dict[str, Any] | None) -> dict[str, Any]:
    src = prefs or {}
    payload = {k: src[k] for k in EXTRA_KEYS if k in src}
    path = prefs_path(user_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        return {}
    return payload


def merge_extras(user_id: Optional[str], prefs: dict[str, Any] | None) -> dict[str, Any]:
    """Overlay the locally stored extras onto a cloud-loaded prefs dict."""
    out = dict(prefs or {})
    for key, value in read_extras(user_id).items():
        out[key] = value
    return out
