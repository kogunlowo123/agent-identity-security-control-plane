"""ACL filter — removes chunks the requesting agent cannot access."""

from __future__ import annotations

import logging

from rag_core.stores.vector_base import ScoredChunk

logger = logging.getLogger(__name__)


def acl_filter(chunks: list[ScoredChunk], agent_tier: str, classification: str | None = None) -> list[ScoredChunk]:
    """Filter out chunks the requesting agent tier cannot access."""
    TIER_ORDER = {"T0": 0, "T1": 1, "T2": 2, "T3": 3}
    agent_level = TIER_ORDER.get(agent_tier, 3)
    allowed = []
    for chunk in chunks:
        allowed_tiers = chunk.metadata.get("allowed_tiers", ["T0", "T1", "T2", "T3"])
        chunk_min_level = min(TIER_ORDER.get(t, 3) for t in allowed_tiers)
        if agent_level <= chunk_min_level:
            if classification:
                chunk_classification = chunk.metadata.get("classification", "internal")
                CLASSIFICATION_ORDER = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
                if CLASSIFICATION_ORDER.get(classification, 0) < CLASSIFICATION_ORDER.get(chunk_classification, 1):
                    continue
            allowed.append(chunk)
    filtered = len(chunks) - len(allowed)
    if filtered > 0:
        logger.debug("ACL filter removed %d/%d chunks for tier %s", filtered, len(chunks), agent_tier)
    return allowed
