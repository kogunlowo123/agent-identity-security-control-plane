"""Document sync pipeline: load → chunk → embed → store."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DocumentSync:
    """Orchestrates load → chunk → enrich → embed → index pipeline."""

    def __init__(self, chunker: Any, embedder: Any, vector_store: Any, bm25_store: Any) -> None:
        self._chunker = chunker
        self._embedder = embedder
        self._vector_store = vector_store
        self._bm25_store = bm25_store

    async def sync_document(self, content: str, metadata: dict) -> int:
        chunks = self._chunker.chunk(content, metadata)
        texts = [c["text"] for c in chunks]
        embeddings = await self._embedder.embed_batch(texts)
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding
        await self._vector_store.upsert(chunks)
        await self._bm25_store.upsert(chunks)
        logger.info("Synced %d chunks for source=%s", len(chunks), metadata.get("source", "unknown"))
        return len(chunks)
