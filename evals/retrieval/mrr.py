"""Mean Reciprocal Rank (MRR) evaluation metric."""

from __future__ import annotations


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """Compute Reciprocal Rank for a single query."""
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def mean_reciprocal_rank(results: list[tuple[list[str], set[str]]]) -> float:
    """Compute MRR across multiple queries."""
    if not results:
        return 0.0
    return sum(reciprocal_rank(r, rel) for r, rel in results) / len(results)


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) < 2:
        print("Usage: python mrr.py <results.json>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        data = json.load(f)
    pairs = [(item["retrieved"], set(item["relevant"])) for item in data]
    score = mean_reciprocal_rank(pairs)
    print(f"MRR: {score:.4f}")
