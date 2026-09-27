"""ACL stamping for RAG chunks — assigns read permissions at ingest time."""

from __future__ import annotations

from typing import Any


def stamp_acl(
    chunk: dict[str, Any],
    classification: str = "internal",
    allowed_tiers: list[str] | None = None,
    owner_team: str | None = None,
) -> dict[str, Any]:
    """Stamp a chunk with access control metadata."""
    chunk["metadata"]["classification"] = classification
    chunk["metadata"]["allowed_tiers"] = allowed_tiers or ["T0", "T1", "T2", "T3"]
    if owner_team:
        chunk["metadata"]["owner_team"] = owner_team
    return chunk
