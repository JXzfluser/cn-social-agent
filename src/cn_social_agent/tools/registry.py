"""Tool registry for the slim workbench agent."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

AsyncHandler = Callable[..., Awaitable[Any]]


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time": self.execution_time,
        }


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    handler: Optional[AsyncHandler] = None

    def validate_parameters(self, params: dict[str, Any]) -> Optional[str]:
        required = self.parameters.get("required", [])
        for req in required:
            if req not in params:
                return f"Missing required parameter: {req}"
        return None

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters.get("properties", {}),
                    "required": self.parameters.get("required", []),
                },
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in self._tools.values()
        ]

    def openai_tools(self) -> list[dict[str, Any]]:
        return [t.openai_schema() for t in self._tools.values()]

    async def execute(self, name: str, params: dict[str, Any]) -> ToolResult:
        start = time.time()
        tool = self.get(name)
        if tool is None:
            return ToolResult(False, error=f"Tool '{name}' not found")
        err = tool.validate_parameters(params)
        if err:
            return ToolResult(False, error=err)
        if tool.handler is None:
            return ToolResult(False, error=f"Tool '{name}' has no handler")
        try:
            data = await tool.handler(**params)
            return ToolResult(True, data=data, execution_time=time.time() - start)
        except Exception as exc:  # noqa: BLE001 — surface to model
            return ToolResult(False, error=str(exc), execution_time=time.time() - start)
