"""Per-request Fast/Strong model routing (does not switch provider)."""

from __future__ import annotations

from typing import Any


def _norm(s: str | None) -> str:
    return (s or "").strip()


def pick_default_fast(models: list[str], fallback: str = "") -> str:
    ids = [m for m in models if m]
    if not ids:
        return fallback
    for needle in ("1.5-flash", "flash-lite", "mini", "small", "highspeed"):
        for m in ids:
            if needle in m.lower() and "pro" not in m.lower() and "video" not in m.lower():
                return m
    for m in ids:
        low = m.lower()
        if "flash" in low and "pro" not in low and "image" not in low and "video" not in low:
            return m
    return ids[0]


def pick_default_strong(models: list[str], fallback: str = "") -> str:
    ids = [m for m in models if m]
    if not ids:
        return fallback
    for needle in ("2.5-pro", "2.5-flash", "pro", "2.0-flash"):
        for m in ids:
            low = m.lower()
            if needle in low and "image" not in low and "video" not in low:
                return m
    # Prefer later / larger-looking ids
    chat = [m for m in ids if "image" not in m.lower() and "video" not in m.lower()]
    return (chat[-1] if chat else ids[-1]) or fallback


def resolve_chat_model(
    *,
    agent_mode: str,
    prefs: dict[str, Any] | None,
    available_models: list[str] | None = None,
    default_model: str = "",
    session_model: str = "",
    body_model: str = "",
) -> dict[str, str]:
    """Pick model for one chat turn.

    Returns keys: model, tier (fast|strong|fixed|override), reason.
    Session/body override always wins.
    """
    prefs = prefs or {}
    models = [str(m).strip() for m in (available_models or []) if str(m).strip()]
    override = _norm(body_model) or _norm(session_model)
    if override:
        return {
            "model": override,
            "tier": "override",
            "reason": "会话或请求指定模型",
        }

    route = _norm(prefs.get("llm_route")).lower() or "smart"
    pinned = _norm(prefs.get("llm_model")) or _norm(default_model)
    fast = _norm(prefs.get("llm_model_fast")) or pick_default_fast(models, pinned)
    strong = _norm(prefs.get("llm_model_strong")) or pick_default_strong(models, pinned)

    if route == "fixed":
        model = pinned or strong or fast
        return {
            "model": model,
            "tier": "fixed",
            "reason": "固定模型",
        }

    # smart
    if (agent_mode or "").lower() == "produce":
        return {
            "model": strong or pinned or fast,
            "tier": "strong",
            "reason": "制片/工具任务 → Strong",
        }
    return {
        "model": fast or pinned or strong,
        "tier": "fast",
        "reason": "对话研究 → Fast",
    }
