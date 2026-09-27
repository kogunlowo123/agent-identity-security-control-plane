"""Metadata enrichment for RAG chunks."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


def enrich_metadata(chunk: dict[str, Any], source_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Adds standard metadata fields to a chunk."""
    meta = chunk.get("metadata", {})
    text = chunk.get("text", "")
    meta.update({
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "content_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
        "char_count": len(text),
        "word_count": len(text.split()),
    })
    if source_metadata:
        meta.update(source_metadata)
    chunk["metadata"] = meta
    return chunk
