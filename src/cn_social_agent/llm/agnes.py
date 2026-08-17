"""Agnes AI LLM adapter (OpenAI-compatible chat completions)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional
import time

import httpx
import yaml


def _key_from_yaml() -> str:
    """Fallback to config/default.yaml llm.api_key when env is empty."""
    root = Path(__file__).resolve().parents[3]
    for name in ("local.yaml", "dev.yaml", "default.yaml"):
        path = root / "config" / name
        if not path.is_file():
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            llm = data.get("llm") or {}
            if (llm.get("provider") or "").lower() in ("", "agnes"):
                key = (llm.get("api_key") or "").strip()
                if key:
                    return key
        except Exception:  # noqa: BLE001
            continue
    return ""


def _model_from_yaml() -> str:
    root = Path(__file__).resolve().parents[3]
    for name in ("local.yaml", "dev.yaml", "default.yaml"):
        path = root / "config" / name
        if not path.is_file():
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            model = ((data.get("llm") or {}).get("model") or "").strip()
            if model:
                return model
        except Exception:  # noqa: BLE001
            continue
    return ""


class AgnesLLM:
    """Async Agnes chat client compatible with AgentLoop.LLMClient."""

    DEFAULT_BASE = "https://apihub.agnes-ai.com/v1"
    DEFAULT_MODEL = "agnes-2.0-flash"
    # Used when /v1/models is unreachable
    FALLBACK_CHAT_MODELS = (
        "agnes-2.5-flash",
        "agnes-2.5-pro",
        "agnes-2.0-flash",
        "agnes-1.5-flash",
    )
    _models_cache: list[str] | None = None
    _models_cache_at: float = 0.0
    _MODELS_TTL_SEC = 300.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv("AGNES_API_KEY")
            or os.getenv("LLM_API_KEY")
            or _key_from_yaml()
        )
        self.model = (
            model
            or os.getenv("AGNES_MODEL")
            or os.getenv("WORKBENCH_MODEL")
            or _model_from_yaml()
            or self.DEFAULT_MODEL
        )
        self.base_url = (
            base_url
            or os.getenv("AGNES_BASE_URL")
            or self.DEFAULT_BASE
        ).rstrip("/")

    @classmethod
    def configured(cls) -> bool:
        return bool(
            os.getenv("AGNES_API_KEY")
            or os.getenv("LLM_API_KEY")
            or _key_from_yaml()
        )

    @staticmethod
    def _is_chat_model_id(model_id: str) -> bool:
        mid = (model_id or "").strip().lower()
        if not mid:
            return False
        if any(x in mid for x in ("image", "video", "tts", "whisper", "embedding", "embed")):
            return False
        return True

    async def list_models(self, *, limit: int = 80) -> list[dict[str, Any]]:
        """GET OpenAI-compatible /v1/models; returns raw data rows."""
        if not self.api_key:
            return []
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=20.0, trust_env=False) as client:
            try:
                resp = await client.get(f"{self.base_url}/models", headers=headers)
            except httpx.HTTPError:
                return []
            if resp.is_error:
                return []
            data = resp.json()
        rows = data.get("data") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            return []
        out: list[dict[str, Any]] = []
        for row in rows[: max(1, limit)]:
            if isinstance(row, dict):
                mid = str(row.get("id") or row.get("name") or "").strip()
                if mid:
                    out.append(row if row.get("id") else {**row, "id": mid})
            elif isinstance(row, str) and row.strip():
                out.append({"id": row.strip()})
        return out

    async def list_chat_model_ids(self, *, limit: int = 80, force: bool = False) -> list[str]:
        """Chat-capable model ids, newest-ish first; falls back to catalog."""
        now = time.monotonic()
        cls = type(self)
        if (
            not force
            and cls._models_cache
            and (now - cls._models_cache_at) < cls._MODELS_TTL_SEC
        ):
            return list(cls._models_cache)[:limit]

        rows = await self.list_models(limit=limit * 2)
        ids: list[str] = []
        for row in rows:
            mid = str(row.get("id") or "").strip()
            if self._is_chat_model_id(mid) and mid not in ids:
                ids.append(mid)
            if len(ids) >= limit:
                break
        if not ids:
            ids = [m for m in self.FALLBACK_CHAT_MODELS if self._is_chat_model_id(m)]
        preferred: list[str] = []
        for m in (
            "agnes-2.5-flash",
            "agnes-2.5-pro",
            self.DEFAULT_MODEL,
            "agnes-2.0-flash",
            "agnes-1.5-flash",
        ):
            if m in ids and m not in preferred:
                preferred.append(m)
        rest = [m for m in ids if m not in preferred]
        ordered = preferred + rest
        cls._models_cache = ordered
        cls._models_cache_at = now
        return list(ordered)[:limit]
    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str = "",
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(
                "AGNES_API_KEY is not set (also checked config/default.yaml llm.api_key)"
            )

        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        # AgentLoop currently consumes full JSON responses (non-stream).
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=90.0, trust_env=False) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
            except httpx.TimeoutException as exc:
                raise RuntimeError(
                    f"Agnes LLM timeout ({type(exc).__name__}) after 90s"
                ) from exc
            except httpx.HTTPError as exc:
                raise RuntimeError(
                    f"Agnes LLM network error: {type(exc).__name__}: {exc or 'no message'}"
                ) from exc
            if resp.is_error:
                raise RuntimeError(f"Agnes error {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
            if not data.get("choices"):
                raise RuntimeError(f"Agnes empty choices: {data}")
            return data
