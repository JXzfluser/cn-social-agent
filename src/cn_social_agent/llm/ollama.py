"""Ollama LLM adapter for AgentLoop."""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx


class OllamaLLM:
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434"
        ).rstrip("/")
        self.model = model or os.getenv("WORKBENCH_MODEL") or os.getenv(
            "OLLAMA_MODEL", "gemma2:2b"
        )

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
        # Ollama OpenAI-compatible endpoint.
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": [
                {"role": m.get("role", "user"), "content": m.get("content") or ""}
                for m in messages
                if m.get("role") in ("system", "user", "assistant")
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        # Tool calling support varies by model; omit tools for broad compatibility.
        async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
            )
            if resp.is_error:
                # Fallback to native /api/chat
                native = {
                    "model": payload["model"],
                    "messages": payload["messages"],
                    "stream": False,
                    "options": payload["options"],
                }
                resp2 = await client.post(f"{self.base_url}/api/chat", json=native)
                if resp2.is_error:
                    raise RuntimeError(
                        f"Ollama error {resp.status_code}/{resp2.status_code}: "
                        f"{resp.text[:200]} | {resp2.text[:200]}"
                    )
                data = resp2.json()
                content = (data.get("message") or {}).get("content", "")
                return {
                    "choices": [
                        {"message": {"role": "assistant", "content": content}}
                    ]
                }
            return resp.json()

    @staticmethod
    async def available(base_url: Optional[str] = None) -> bool:
        url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip(
            "/"
        )
        try:
            async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
                resp = await client.get(f"{url}/api/tags")
                return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    async def list_model_ids(
        base_url: Optional[str] = None, *, limit: int = 40
    ) -> list[str]:
        url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip(
            "/"
        )
        try:
            async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
                resp = await client.get(f"{url}/api/tags")
                if resp.is_error:
                    return []
                data = resp.json()
            models = data.get("models") if isinstance(data, dict) else []
            ids: list[str] = []
            for row in models or []:
                name = ""
                if isinstance(row, dict):
                    name = str(row.get("name") or row.get("model") or "").strip()
                elif isinstance(row, str):
                    name = row.strip()
                if name and name not in ids:
                    ids.append(name)
                if len(ids) >= limit:
                    break
            return ids
        except Exception:  # noqa: BLE001
            return []
