"""Per-user access to the InsForge AI (model) gateway.

Requests are made with the **end user's** JWT, because ``POST
/api/ai/chat/completion`` is a ``verifyUser`` endpoint. Beyond correctness this
gives per-user accounting on the gateway and keeps a single credential chain:
one token identifies the caller to Auth, Database, Storage and AI alike.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Optional

from .tenant import require
from .i18n import output_language_hint

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "openai/gpt-4o-mini"

_SYSTEM_TEMPLATE = (
    "You are {name}, a specialist working inside a multi-tenant expert workbench.\n"
    "{persona}\n"
    "{language}\n"
    "Always answer in the requested language and keep the requested structure."
)


class AiError(RuntimeError):
    pass


class TenantAI:
    """Chat completions issued on behalf of the bound tenant."""

    def __init__(self, client: Any, model: str = DEFAULT_MODEL) -> None:
        self._client = client
        self.model = client.config.llm.default_model or model

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {require().token}"}

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Return the assistant message content."""
        try:
            data = await self._client.api_post(
                "/api/ai/chat/completion",
                json_body={
                    "model": model or self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False,
                },
                headers=self._headers(),
                base="api",
                use_auth=False,
            )
        except Exception as exc:  # noqa: BLE001
            raise AiError(f"chat completion failed: {exc}") from exc
        return _extract_content(data)

    async def chat_json(
        self,
        messages: list[dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 2048,
    ) -> Any:
        """Chat and parse the assistant reply as JSON (tolerant of fences)."""
        raw = await self.chat(
            messages, model=model, temperature=temperature, max_tokens=max_tokens
        )
        return _parse_json(raw)

    async def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """Yield text deltas from an SSE stream."""
        resp = await self._client.api_request(
            "POST",
            "/api/ai/chat/completion",
            json_body={
                "model": model or self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            },
            headers={**self._headers(), "Accept": "text/event-stream"},
            base="api",
            use_auth=False,
        )
        if resp.is_error:
            raise AiError(f"stream failed ({resp.status_code}): {resp.text}")
        async for line in resp.aiter_lines():
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload in ("[DONE]", "DONE"):
                break
            try:
                event = json.loads(payload)
            except ValueError:
                continue
            delta = event.get("text") or event.get("content") or event.get("delta")
            if not delta:
                choices = event.get("choices") or []
                if choices:
                    delta = choices[0].get("delta", {}).get("content")
            if delta:
                yield str(delta)

    def system_prompt(
        self,
        name: str,
        persona: str,
        locale: Optional[str] = None,
    ) -> str:
        return _SYSTEM_TEMPLATE.format(
            name=name,
            persona=persona.strip(),
            language=output_language_hint(locale),
        )


def _extract_content(data: Any) -> str:
    if isinstance(data, str):
        return data
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if content:
            return str(content)
    for key in ("content", "text", "message"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _parse_json(raw: str) -> Any:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except ValueError as exc:
        raise AiError(f"model did not return parseable JSON: {raw[:400]}") from exc


def tenant_ai(client: Any) -> TenantAI:
    return TenantAI(client)
