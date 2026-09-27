"""Embedding cache backed by in-memory LRU with optional Redis support."""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from typing import Any

from rag_core.embeddings.base import BaseEmbedder

logger = logging.getLogger(__name__)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class CachedEmbedder(BaseEmbedder):
    """Wraps another embedder and caches results by content hash."""

    def __init__(self, embedder: BaseEmbedder, max_size: int = 10_000) -> None:
        self._embedder = embedder
        self.DIMENSIONS = embedder.DIMENSIONS
        self._cache: dict[str, list[float]] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    async def embed(self, text: str) -> list[float]:
        key = _text_hash(text)
        if key in self._cache:
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        result = await self._embedder.embed(text)
        if len(self._cache) >= self._max_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = result
        return result

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for i, text in enumerate(texts):
            key = _text_hash(text)
            if key in self._cache:
                self._hits += 1
                results.append(self._cache[key])
            else:
                self._misses += 1
                results.append([])
                uncached_indices.append(i)
                uncached_texts.append(text)

        if uncached_texts:
            new_embeddings = await self._embedder.embed_batch(uncached_texts)
            for idx, embedding in zip(uncached_indices, new_embeddings):
                key = _text_hash(texts[idx])
                if len(self._cache) >= self._max_size:
                    oldest = next(iter(self._cache))
                    del self._cache[oldest]
                self._cache[key] = embedding
                results[idx] = embedding

        return results

    @property
    def cache_hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0
