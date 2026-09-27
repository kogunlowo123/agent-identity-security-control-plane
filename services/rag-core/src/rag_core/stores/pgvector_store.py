"""pgvector-backed vector store using asyncpg."""

from __future__ import annotations

import json
import logging
from typing import Any

from rag_core.stores.vector_base import BaseVectorStore, ScoredChunk

logger = logging.getLogger(__name__)


class PgVectorStore(BaseVectorStore):
    """Vector store using PostgreSQL + pgvector extension."""

    def __init__(self, dsn: str, table: str = "rag_chunks", dimensions: int = 1024) -> None:
        self._dsn = dsn
        self._table = table
        self._dimensions = dimensions
        self._pool: Any = None

    async def _get_pool(self) -> Any:
        if self._pool is None:
            try:
                import asyncpg
                self._pool = await asyncpg.create_pool(self._dsn, min_size=2, max_size=10)
            except ImportError as exc:
                raise ImportError("asyncpg required: pip install asyncpg") from exc
        return self._pool

    async def upsert(self, chunks: list[dict]) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            for chunk in chunks:
                embedding = chunk.get("embedding")
                if not embedding:
                    continue
                embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
                await conn.execute(
                    f"""
                    INSERT INTO {self._table} (chunk_id, content, embedding, metadata)
                    VALUES ($1, $2, $3::vector, $4::jsonb)
                    ON CONFLICT (chunk_id) DO UPDATE
                    SET content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata
                    """,
                    chunk["chunk_id"],
                    chunk["text"],
                    embedding_str,
                    json.dumps(chunk.get("metadata", {})),
                )

    async def search(self, query_embedding: list[float], top_k: int = 10, filters: dict | None = None) -> list[ScoredChunk]:
        pool = await self._get_pool()
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT chunk_id, content, metadata,
                       1 - (embedding <=> $1::vector) AS score
                FROM {self._table}
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                embedding_str,
                top_k,
            )
        return [
            ScoredChunk(
                chunk_id=row["chunk_id"],
                text=row["content"],
                score=float(row["score"]),
                metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else dict(row["metadata"]),
                rank=i + 1,
            )
            for i, row in enumerate(rows)
        ]

    async def delete(self, chunk_id: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(f"DELETE FROM {self._table} WHERE chunk_id = $1", chunk_id)
