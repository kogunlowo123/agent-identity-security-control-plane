"""Parent-child chunker — large parent chunks with smaller child chunks for retrieval."""

from __future__ import annotations

import uuid
from typing import Any

from rag_core.chunking.base import BaseChunker
from rag_core.chunking.recursive import RecursiveChunker


class ParentChildChunker(BaseChunker):
    """Produces large parent chunks and small child chunks.

    Child chunks are used for retrieval; parent chunks are returned as context.
    """

    def __init__(self, parent_size: int = 1024, child_size: int = 256, overlap: int = 32) -> None:
        self._parent_chunker = RecursiveChunker(chunk_size=parent_size, overlap=overlap)
        self._child_chunker = RecursiveChunker(chunk_size=child_size, overlap=overlap)

    def chunk(self, text: str, metadata: dict[str, Any]) -> list[dict]:
        """Returns child chunks with parent_id in metadata for retrieval."""
        parent_chunks = self._parent_chunker.chunk(text, metadata)
        all_children: list[dict] = []
        for parent in parent_chunks:
            parent_id = parent["chunk_id"]
            children = self._child_chunker.chunk(parent["text"], parent["metadata"])
            for child in children:
                child["metadata"]["parent_id"] = parent_id
                child["metadata"]["parent_text"] = parent["text"]
                all_children.append(child)
        return all_children
