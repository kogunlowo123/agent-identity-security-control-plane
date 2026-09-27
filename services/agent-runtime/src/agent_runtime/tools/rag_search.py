"""RAG search tool for agent runtime."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from agent_runtime.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class RAGSearchTool(BaseTool):
    """Search the RAG knowledge base using hybrid retrieval."""

    name = "rag_search"
    description = "Search the RAG knowledge base for relevant context about agent identities."
    required_capabilities = ["rag:search"]

    def __init__(self, rag_core_url: str, top_k: int = 10) -> None:
        self._rag_core_url = rag_core_url.rstrip("/")
        self._top_k = top_k

    async def run(self, query: str, top_k: int | None = None, **kwargs: Any) -> ToolResult:
        k = top_k or self._top_k
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._rag_core_url}/retrieve",
                    json={"query": query, "top_k": k},
                )
                resp.raise_for_status()
                data = resp.json()
                chunks = data.get("chunks", [])
                return ToolResult.ok(
                    data=chunks,
                    metadata={"query": query, "top_k": k, "returned": len(chunks)},
                )
        except httpx.HTTPStatusError as exc:
            logger.error("RAG search HTTP error: %s", exc)
            return ToolResult.fail(f"RAG search failed: {exc.response.status_code}")
        except httpx.RequestError as exc:
            logger.error("RAG search connection error: %s", exc)
            return ToolResult.fail(f"RAG search connection error: {exc}")
