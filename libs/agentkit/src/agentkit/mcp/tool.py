"""MCP Tool base class — every agent tool inherits from this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    """Structured result returned by any MCPTool."""

    content: Any = None
    error: str | None = None
    metadata: dict[str, Any] = {}

    @property
    def ok(self) -> bool:
        return self.error is None


class MCPTool(ABC):
    """
    Base class for all MCP tools.

    Subclass and implement:
      - name: str property
      - description: str property
      - input_schema: dict (JSON Schema for the input)
      - execute(**kwargs) -> ToolResult
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult: ...

    def to_dict(self) -> dict[str, Any]:
        """Serialise to MCP tool-definition format (for LLM tool-use)."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }
