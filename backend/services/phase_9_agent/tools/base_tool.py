"""Base class + shared types for Phase 9 investigation tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolOutput:
    """Uniform return type for every tool.  Kept tiny on purpose so the
    LLM can ingest it cheaply.

    ``data`` is whatever the tool wants to expose; the agent will redact
    it before forwarding to the LLM.  ``error`` is non-empty only on
    failure paths.
    """

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """Serialisable view sent back to the LLM as a tool-call result."""
        if self.success:
            return {"ok": True, "data": self.data}
        return {"ok": False, "error": self.error or "unknown_error", "data": self.data}


class BaseTool(ABC):
    """Abstract investigation tool.

    Subclasses must define:
        name                — unique identifier exposed to the LLM
        description         — what the tool does, written for the model
        get_function_schema — OpenAI-compatible function definition
        execute(input)      — async coroutine that does the work
    """

    name: str = ""
    description: str = ""

    def get_function_schema(self) -> dict[str, Any]:
        """Wrap ``get_input_schema`` into OpenAI's tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_input_schema(),
            },
        }

    @abstractmethod
    def get_input_schema(self) -> dict[str, Any]:
        """JSON-schema dict describing the tool's inputs."""

    @abstractmethod
    async def execute(self, input_data: dict[str, Any]) -> ToolOutput:
        """Run the tool.  Must never raise — wrap errors into ``ToolOutput(success=False)``."""
