"""Reciprocal Rank Fusion (RRF) for hybrid search result merging."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .hybrid import Chunk, ScoredChunk


def reciprocal_rank_fusion(
    bm25_results: list["Chunk"],
    dense_results: list["Chunk"],
    k: int = 60,
) -> list["ScoredChunk"]:
    """
    Merge BM25 and dense retrieval results using Reciprocal Rank Fusion.

    RRF score = sum(1 / (k + rank_i)) for each result list where the document appears.

    Args:
        bm25_results: Ranked list from BM25 retrieval
        dense_results: Ranked list from dense retrieval
        k: RRF smoothing constant (default 60, per Cormack et al. 2009)

    Returns:
        Merged and sorted list of ScoredChunk objects
    """
    from .hybrid import ScoredChunk

    # Build a lookup from chunk_id to Chunk object
    all_chunks: dict[str, "Chunk"] = {}
    for chunk in bm25_results:
        all_chunks[chunk.chunk_id] = chunk
    for chunk in dense_results:
        all_chunks[chunk.chunk_id] = chunk

    # Compute RRF scores
    rrf_scores: dict[str, float] = {}
    bm25_ranks: dict[str, int] = {}
    dense_ranks: dict[str, int] = {}

    for rank, chunk in enumerate(bm25_results, start=1):
        rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank)
        bm25_ranks[chunk.chunk_id] = rank

    for rank, chunk in enumerate(dense_results, start=1):
        rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank)
        dense_ranks[chunk.chunk_id] = rank

    # Build ScoredChunk list and sort by RRF score descending
    scored = [
        ScoredChunk(
            chunk=all_chunks[chunk_id],
            bm25_rank=bm25_ranks.get(chunk_id),
            dense_rank=dense_ranks.get(chunk_id),
            rrf_score=score,
        )
        for chunk_id, score in rrf_scores.items()
    ]
    scored.sort(key=lambda sc: sc.rrf_score, reverse=True)
    return scored
