"""OAuth tokens + platform config — InsForge Secrets first, local file fallback."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

# Optional InsForge secrets client set by AppState at startup
_secrets: Any = None
_secrets_ok: Optional[bool] = None  # None=unknown, True/False after probe


def set_secrets_backend(secrets: Any) -> None:
    global _secrets, _secrets_ok
    _secrets = secrets
    _secrets_ok = None


def get_secrets_backend() -> Any:
    return _secrets


def secrets_backend_status() -> dict[str, Any]:
    return {
        "backend": "insforge" if _secrets is not None else "local",
        "insforge_ok": _secrets_ok,
        "message": (
            "凭证写入 InsForge Secrets"
            if _secrets is not None and _secrets_ok is not False
            else "InsForge Secrets 不可用，已用本地 data/oauth 降级"
            if _secrets is not None
            else "未连接 InsForge，凭证保存在本地 data/oauth"
        ),
    }


def oauth_dir() -> Path:
    root = Path(__file__).resolve().parents[3]
    d = root / "data" / "oauth"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_@.+-]+", "_", (s or "").strip())[:96] or "anon"


def _secret_safe(s: str) -> str:
    """InsForge secret keys: uppercase letters, numbers, underscores only."""
    raw = re.sub(r"[^a-zA-Z0-9]+", "_", (s or "").strip()).strip("_")
    return (raw.upper()[:80] or "ANON")


def token_path(platform: str, owner: str) -> Path:
    p = oauth_dir() / _safe(platform)
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{_safe(owner)}.json"


def secret_key_token(platform: str, owner: str) -> str:
    return f"CARD_OAUTH_{_secret_safe(platform)}_{_secret_safe(owner)}"


def secret_key_config(platform: str) -> str:
    return f"CARD_PLAT_CFG_{_secret_safe(platform)}"


async def _upsert_secret(key: str, value: str) -> bool:
    global _secrets_ok
    secrets = _secrets
    if secrets is None:
        return False
    try:
        updated = await secrets.update_secret(key, value)
        if updated is None:
            await secrets.create_secret(key, value)
        _secrets_ok = True
        return True
    except Exception:  # noqa: BLE001
        _secrets_ok = False
        return False


async def _get_secret(key: str) -> Optional[str]:
    global _secrets_ok
    secrets = _secrets
    if secrets is None:
        return None
    try:
        val = await secrets.get_secret(key)
        if _secrets_ok is None:
            _secrets_ok = True
        return val
    except Exception:  # noqa: BLE001
        _secrets_ok = False
        return None


async def _delete_secret(key: str) -> bool:
    global _secrets_ok
    secrets = _secrets
    if secrets is None:
        return False
    try:
        await secrets.delete_secret(key)
        return True
    except Exception:  # noqa: BLE001
        _secrets_ok = False
        return False


async def probe_secrets_backend() -> dict[str, Any]:
    """Try a harmless upsert to verify InsForge Secrets key format / availability."""
    global _secrets_ok
    if _secrets is None:
        _secrets_ok = False
        return secrets_backend_status()
    ok = await _upsert_secret("CARD_PUBLISH_PROBE", "1")
    _secrets_ok = ok
    return secrets_backend_status()


async def save_token(platform: str, owner: str, data: dict[str, Any]) -> None:
    raw = json.dumps(data, ensure_ascii=False)
    await _upsert_secret(secret_key_token(platform, owner), raw)
    # Always mirror to disk as offline fallback
    token_path(platform, owner).write_text(raw, encoding="utf-8")


async def load_token(platform: str, owner: str) -> Optional[dict[str, Any]]:
    raw = await _get_secret(secret_key_token(platform, owner))
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:  # noqa: BLE001
            pass
    path = token_path(platform, owner)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


async def clear_token(platform: str, owner: str) -> bool:
    await _delete_secret(secret_key_token(platform, owner))
    path = token_path(platform, owner)
    if path.is_file():
        path.unlink()
        return True
    return False


async def save_platform_config(platform: str, data: dict[str, Any]) -> bool:
    """Persist backend platform credentials (app_id/secret) to InsForge (+ local)."""
    raw = json.dumps(data, ensure_ascii=False)
    ok = await _upsert_secret(secret_key_config(platform), raw)
    cfg_dir = oauth_dir() / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / f"{_safe(platform)}.json").write_text(raw, encoding="utf-8")
    return ok


async def load_platform_config(platform: str) -> dict[str, Any]:
    raw = await _get_secret(secret_key_config(platform))
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:  # noqa: BLE001
            pass
    path = oauth_dir() / "config" / f"{_safe(platform)}.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:  # noqa: BLE001
            pass
    return {}


def mask_secret(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) <= 8:
        return "••••"
    return v[:4] + "••••" + v[-4:]
