"""Recursive character text splitter."""

from __future__ import annotations

import uuid
from typing import Any

from rag_core.chunking.base import BaseChunker

SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


class RecursiveChunker(BaseChunker):
    def __init__(self, chunk_size: int = 512, overlap: int = 64) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap

    def _split(self, text: str, separators: list[str]) -> list[str]:
        if not separators:
            return [text[i:i + self._chunk_size] for i in range(0, len(text), self._chunk_size - self._overlap)]
        sep = separators[0]
        splits = text.split(sep)
        chunks: list[str] = []
        current = ""
        for part in splits:
            candidate = current + (sep if current else "") + part
            if len(candidate) <= self._chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(part) > self._chunk_size:
                    chunks.extend(self._split(part, separators[1:]))
                    current = ""
                else:
                    current = part
        if current:
            chunks.append(current)
        return [c for c in chunks if c.strip()]

    def chunk(self, text: str, metadata: dict[str, Any]) -> list[dict]:
        raw_chunks = self._split(text, SEPARATORS)
        result = []
        for i, chunk_text in enumerate(raw_chunks):
            result.append({
                "chunk_id": str(uuid.uuid4()),
                "text": chunk_text.strip(),
                "metadata": {**metadata, "chunk_index": i, "total_chunks": len(raw_chunks)},
            })
        return result
