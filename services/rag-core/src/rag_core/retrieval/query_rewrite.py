"""Query rewriting for improved retrieval coverage."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def rewrite_query(query: str, llm_client: Any | None = None) -> list[str]:
    """Generate multiple query variants for better retrieval recall.

    If llm_client is None, returns simple keyword-based expansions.
    """
    if llm_client is None:
        return _keyword_expand(query)

    try:
        response = await llm_client.acompletion(
            model="vertex_ai/gemini-1.5-flash",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a query rewriting assistant. Given a search query, "
                        "generate 3 alternative phrasings that would retrieve the same information. "
                        "Return only the queries, one per line."
                    ),
                },
                {"role": "user", "content": query},
            ],
            temperature=0.3,
            max_tokens=256,
        )
        text = response.choices[0].message.content.strip()
        variants = [line.strip() for line in text.splitlines() if line.strip()]
        return [query] + variants[:3]
    except Exception as exc:
        logger.warning("Query rewrite failed, using original: %s", exc)
        return [query]


def _keyword_expand(query: str) -> list[str]:
    """Simple synonym-based expansion for test/fallback."""
    expansions = [query]
    replacements = {
        "identity": "workload identity SPIFFE",
        "token": "JWT bearer token",
        "delegation": "delegate chain authority",
        "agent": "AI agent workload service",
    }
    query_lower = query.lower()
    for keyword, expansion in replacements.items():
        if keyword in query_lower:
            expansions.append(query_lower.replace(keyword, expansion))
            break
    return expansions
