"""Base class for agent tools."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class ToolResult:
    """Structured result from tool execution."""

    def __init__(
        self,
        success: bool,
        data: Any = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.success = success
        self.data = data
        self.error = error
        self.metadata = metadata or {}

    @classmethod
    def ok(cls, data: Any, metadata: dict[str, Any] | None = None) -> "ToolResult":
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def fail(cls, error: str, metadata: dict[str, Any] | None = None) -> "ToolResult":
        return cls(success=False, error=error, metadata=metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseTool(ABC):
    """Abstract base for all agent tools."""

    name: str
    description: str
    required_capabilities: list[str] = []

    def check_capability(self, agent_capabilities: list[str]) -> bool:
        return all(cap in agent_capabilities for cap in self.required_capabilities)

    @abstractmethod
    async def run(self, **kwargs: Any) -> ToolResult:
        """Execute the tool and return a result."""
        raise NotImplementedError
