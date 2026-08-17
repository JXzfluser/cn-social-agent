"""MiniMax LLM adapter for AgentLoop (OpenAI-shaped responses)."""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx


class MiniMaxLLM:
    """Async MiniMax chat client compatible with AgentLoop.LLMClient."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY", "")
        self.model = model or os.getenv("WORKBENCH_MODEL") or os.getenv(
            "LLM_MODEL", "MiniMax-M2.7-highspeed"
        )
        self.base_url = (
            base_url
            or os.getenv("MINIMAX_BASE_URL")
            or "https://api.minimax.chat/v1"
        ).rstrip("/")

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
            raise RuntimeError("MINIMAX_API_KEY is not set")

        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
            resp = await client.post(
                f"{self.base_url}/text/chatcompletion_v2",
                headers=headers,
                json=payload,
            )
            if resp.is_error:
                raise RuntimeError(f"MiniMax error {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
            base = data.get("base_resp") or {}
            code = base.get("status_code", 0)
            if code not in (0, None):
                raise RuntimeError(
                    f"MiniMax API status {code}: {base.get('status_msg', data)}"
                )
            if not data.get("choices"):
                raise RuntimeError(f"MiniMax empty choices: {data}")
            return data
