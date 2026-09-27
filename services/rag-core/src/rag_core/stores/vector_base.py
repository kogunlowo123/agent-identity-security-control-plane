"""Abstract vector store interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ScoredChunk:
    chunk_id: str
    text: str
    score: float
    metadata: dict[str, Any]
    rank: int = 0


class BaseVectorStore(ABC):
    @abstractmethod
    async def upsert(self, chunks: list[dict]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def search(self, query_embedding: list[float], top_k: int = 10, filters: dict | None = None) -> list[ScoredChunk]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, chunk_id: str) -> None:
        raise NotImplementedError
