"""
Hybrid retrieval: parallel BM25 (OpenSearch) + dense (pgvector) with RRF fusion.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from .rrf import reciprocal_rank_fusion

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    chunk_id: str
    content: str
    document_source: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoredChunk:
    chunk: Chunk
    bm25_rank: int | None = None
    dense_rank: int | None = None
    rrf_score: float = 0.0


class HybridRetriever:
    """
    Hybrid retrieval combining BM25 (OpenSearch) and dense vector (pgvector).

    Uses asyncio.gather for parallel execution and RRF for score fusion.
    """

    def __init__(
        self,
        opensearch_url: str,
        database_url: str,
        index_prefix: str = "aicp",
        top_k: int = 10,
        rrf_k: int = 60,
    ) -> None:
        self.opensearch_url = opensearch_url
        self.database_url = database_url
        self.index_prefix = index_prefix
        self.top_k = top_k
        self.rrf_k = rrf_k

    async def _bm25_search(self, query: str) -> list[Chunk]:
        """BM25 lexical search via OpenSearch."""
        try:
            from opensearchpy import AsyncOpenSearch

            client = AsyncOpenSearch(hosts=[self.opensearch_url])
            index = f"{self.index_prefix}-chunks"

            body = {
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["content^2", "metadata.title", "metadata.topics"],
                        "type": "best_fields",
                        "tie_breaker": 0.3,
                    }
                },
                "size": self.top_k * 2,  # fetch more for RRF
                "_source": ["chunk_id", "content", "document_source", "metadata"],
            }

            response = await client.search(index=index, body=body)
            await client.close()

            chunks = []
            for hit in response["hits"]["hits"]:
                src = hit["_source"]
                chunks.append(
                    Chunk(
                        chunk_id=src.get("chunk_id", hit["_id"]),
                        content=src.get("content", ""),
                        document_source=src.get("document_source", ""),
                        score=hit["_score"],
                        metadata=src.get("metadata", {}),
                    )
                )
            return chunks

        except Exception as exc:
            logger.warning("BM25 search failed: %s", exc)
            return []

    async def _dense_search(self, query: str, embedding: list[float] | None = None) -> list[Chunk]:
        """Dense vector search via pgvector."""
        import asyncio
        import json

        if embedding is None:
            return []

        try:
            import asyncpg

            conn = await asyncpg.connect(self.database_url)
            try:
                rows = await conn.fetch(
                    """
                    SELECT chunk_id, content, document_source, metadata,
                           1 - (embedding <=> $1::vector) AS cosine_similarity
                    FROM rag_chunks
                    ORDER BY embedding <=> $1::vector
                    LIMIT $2
                    """,
                    json.dumps(embedding),
                    self.top_k * 2,
                )
            finally:
                await conn.close()

            return [
                Chunk(
                    chunk_id=str(row["chunk_id"]),
                    content=row["content"],
                    document_source=row["document_source"],
                    score=float(row["cosine_similarity"]),
                    metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else dict(row["metadata"]),
                )
                for row in rows
            ]

        except Exception as exc:
            logger.warning("Dense search failed: %s", exc)
            return []

    async def retrieve(
        self,
        query: str,
        query_embedding: list[float] | None = None,
        top_k: int | None = None,
    ) -> list[ScoredChunk]:
        """
        Perform hybrid retrieval with RRF fusion.

        Args:
            query: Text query for BM25 search
            query_embedding: Pre-computed query embedding for dense search
            top_k: Number of results to return (defaults to self.top_k)

        Returns:
            List of ScoredChunk sorted by RRF score descending
        """
        k = top_k or self.top_k

        # Parallel retrieval
        bm25_results, dense_results = await asyncio.gather(
            self._bm25_search(query),
            self._dense_search(query, query_embedding),
            return_exceptions=False,
        )

        # RRF fusion
        fused = reciprocal_rank_fusion(
            bm25_results=bm25_results,
            dense_results=dense_results,
            k=self.rrf_k,
        )

        return fused[:k]
