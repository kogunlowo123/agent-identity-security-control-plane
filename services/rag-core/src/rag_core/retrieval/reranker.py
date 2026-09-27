"""Cross-encoder reranker for retrieved chunks."""

from __future__ import annotations

import logging
from typing import Any

from rag_core.stores.vector_base import ScoredChunk

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Reranks chunks using a cross-encoder model."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self._model_name = model_name
        self._model: Any = None

    def _load(self) -> None:
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self._model_name)
            except ImportError as exc:
                raise ImportError("sentence-transformers required") from exc

    def rerank(self, query: str, chunks: list[ScoredChunk], top_k: int | None = None) -> list[ScoredChunk]:
        if not chunks:
            return []
        self._load()
        pairs = [[query, c.text] for c in chunks]
        scores = self._model.predict(pairs)
        reranked = sorted(
            zip(chunks, scores),
            key=lambda x: x[1],
            reverse=True,
        )
        result = []
        limit = top_k or len(chunks)
        for rank, (chunk, score) in enumerate(reranked[:limit], start=1):
            chunk.score = float(score)
            chunk.rank = rank
            result.append(chunk)
        return result
