from __future__ import annotations

from typing import Any, Optional

from .client import InsForgeClient

# Prefer these ids when truncating the OpenRouter catalog for the UI.
_PREFERRED_MODELS = (
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "openai/gpt-4.1-mini",
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-sonnet-4",
    "google/gemini-2.0-flash-001",
    "google/gemini-2.5-flash",
    "deepseek/deepseek-chat",
    "qwen/qwen-2.5-72b-instruct",
)


class InsForgeLLM:
    """InsForge Model Gateway API wrapper.

    Uses OpenRouter-compatible API through InsForge's gateway:
      POST /api/ai/chat/completion
      GET  /api/ai/models
    """

    def __init__(self, client: InsForgeClient):
        self._client = client
        self._api_key = client.config.llm.api_key
        self.model = client.config.llm.default_model or "openai/gpt-4o-mini"

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
        if not model:
            model = self.model or self._client.config.llm.default_model

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            body["tools"] = tools
        return await self._client.api_post(
            "/api/ai/chat/completion",
            json_body=body,
        )

    async def chat_completion_direct(
        self,
        messages: list[dict[str, str]],
        model: str = "",
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        """Call OpenRouter directly with InsForge's API key."""
        if not model:
            model = self.model or self._client.config.llm.default_model

        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = await self._client.api_request(
            "POST",
            "https://openrouter.ai/api/v1/chat/completions",
            json_body=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            use_auth=False,
        )
        if resp.is_error:
            raise Exception(f"LLM call failed: {resp.text}")
        return resp.json()

    async def list_models(self) -> list[dict[str, Any]]:
        try:
            raw = await self._client.api_get("/api/ai/models")
        except Exception:
            return []
        if isinstance(raw, list):
            return [m for m in raw if isinstance(m, dict)]
        if isinstance(raw, dict):
            data = raw.get("data") or raw.get("models") or []
            if isinstance(data, list):
                return [m for m in data if isinstance(m, dict)]
        return []

    async def list_model_ids(self, *, limit: int = 80) -> list[str]:
        """Return a truncated, UI-friendly list of OpenRouter model ids."""
        rows = await self.list_models()
        ids: list[str] = []
        seen: set[str] = set()
        for row in rows:
            mid = str(row.get("modelId") or row.get("id") or "").strip()
            if not mid or mid in seen:
                continue
            modalities = row.get("outputModality") or row.get("output_modality") or []
            if modalities and "text" not in modalities and "TEXT" not in modalities:
                continue
            seen.add(mid)
            ids.append(mid)

        preferred = [m for m in _PREFERRED_MODELS if m in seen]
        rest = [m for m in ids if m not in preferred]
        ordered = preferred + rest
        return ordered[: max(1, limit)]

    async def health(self) -> bool:
        try:
            await self._client.api_get("/api/health", use_auth=False)
            return True
        except Exception:
            return False

    async def available(self) -> bool:
        """True when gateway is up and model catalog is reachable (admin auth)."""
        try:
            models = await self.list_models()
            return bool(models)
        except Exception:
            return False
