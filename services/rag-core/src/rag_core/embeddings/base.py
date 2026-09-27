"""Base embedding interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    DIMENSIONS: int = 0

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError
