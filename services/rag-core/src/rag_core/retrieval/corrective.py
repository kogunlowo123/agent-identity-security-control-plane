"""Corrective RAG — grades retrieved chunks and retries if quality is low."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from rag_core.stores.vector_base import ScoredChunk

logger = logging.getLogger(__name__)

RELEVANCE_THRESHOLD = 0.4


@dataclass
class RetrievalGrade:
    chunk_id: str
    relevant: bool
    score: float


def grade_chunk(query: str, chunk: ScoredChunk) -> RetrievalGrade:
    """Simple lexical overlap grader (replace with LLM grader in production)."""
    query_words = set(query.lower().split())
    chunk_words = set(chunk.text.lower().split())
    overlap = len(query_words & chunk_words)
    score = overlap / max(len(query_words), 1)
    return RetrievalGrade(chunk_id=chunk.chunk_id, relevant=score >= RELEVANCE_THRESHOLD, score=score)


def corrective_filter(query: str, chunks: list[ScoredChunk]) -> tuple[list[ScoredChunk], float]:
    """Filter chunks by relevance and return (relevant_chunks, quality_score)."""
    if not chunks:
        return [], 0.0
    grades = [grade_chunk(query, c) for c in chunks]
    relevant = [c for c, g in zip(chunks, grades) if g.relevant]
    quality_score = len(relevant) / len(chunks)
    logger.debug("Corrective filter: %d/%d chunks relevant (score=%.2f)", len(relevant), len(chunks), quality_score)
    return relevant, quality_score
