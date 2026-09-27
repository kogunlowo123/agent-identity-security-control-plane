"""OpenSearch BM25 store for hybrid retrieval."""

from __future__ import annotations

import logging
from typing import Any

from rag_core.stores.vector_base import ScoredChunk

logger = logging.getLogger(__name__)


class OpenSearchStore:
    """BM25 document store backed by OpenSearch."""

    def __init__(self, hosts: list[str], index: str = "rag-chunks") -> None:
        self._hosts = hosts
        self._index = index
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from opensearchpy import AsyncOpenSearch
                self._client = AsyncOpenSearch(hosts=self._hosts)
            except ImportError as exc:
                raise ImportError("opensearch-py required: pip install opensearch-py") from exc
        return self._client

    async def upsert(self, chunks: list[dict]) -> None:
        client = self._get_client()
        actions = []
        for chunk in chunks:
            actions.append({"index": {"_index": self._index, "_id": chunk["chunk_id"]}})
            actions.append({"text": chunk["text"], "metadata": chunk.get("metadata", {})})
        if actions:
            await client.bulk(body=actions)

    async def search(self, query: str, top_k: int = 10, filters: dict | None = None) -> list[ScoredChunk]:
        client = self._get_client()
        body: dict = {
            "query": {"match": {"text": {"query": query, "operator": "or"}}},
            "size": top_k,
        }
        response = await client.search(index=self._index, body=body)
        hits = response["hits"]["hits"]
        return [
            ScoredChunk(
                chunk_id=hit["_id"],
                text=hit["_source"]["text"],
                score=float(hit["_score"]),
                metadata=hit["_source"].get("metadata", {}),
                rank=i + 1,
            )
            for i, hit in enumerate(hits)
        ]

    async def delete(self, chunk_id: str) -> None:
        client = self._get_client()
        await client.delete(index=self._index, id=chunk_id, ignore=[404])
