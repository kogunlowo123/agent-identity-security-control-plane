"""Semantic chunker — splits at embedding-detected topic shifts."""

from __future__ import annotations

import uuid
from typing import Any

from rag_core.chunking.base import BaseChunker

SENTENCE_BOUNDARY = ". "
COSINE_THRESHOLD = 0.85


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class SemanticChunker(BaseChunker):
    """Split text based on semantic similarity between adjacent sentences."""

    def __init__(self, embedder: Any, threshold: float = COSINE_THRESHOLD, min_chunk_chars: int = 100) -> None:
        self._embedder = embedder
        self._threshold = threshold
        self._min_chunk_chars = min_chunk_chars

    def chunk(self, text: str, metadata: dict[str, Any]) -> list[dict]:
        sentences = [s.strip() for s in text.split(SENTENCE_BOUNDARY) if s.strip()]
        if not sentences:
            return []
        if len(sentences) == 1:
            return [{"chunk_id": str(uuid.uuid4()), "text": sentences[0], "metadata": {**metadata, "chunk_index": 0}}]

        import asyncio
        embeddings = asyncio.get_event_loop().run_until_complete(
            self._embedder.embed_batch(sentences)
        )

        chunks: list[str] = []
        current_sents: list[str] = [sentences[0]]
        for i in range(1, len(sentences)):
            sim = _cosine_sim(embeddings[i - 1], embeddings[i])
            if sim < self._threshold and len(" ".join(current_sents)) >= self._min_chunk_chars:
                chunks.append(". ".join(current_sents))
                current_sents = [sentences[i]]
            else:
                current_sents.append(sentences[i])
        if current_sents:
            chunks.append(". ".join(current_sents))

        return [
            {
                "chunk_id": str(uuid.uuid4()),
                "text": c.strip(),
                "metadata": {**metadata, "chunk_index": i, "total_chunks": len(chunks)},
            }
            for i, c in enumerate(chunks) if c.strip()
        ]
