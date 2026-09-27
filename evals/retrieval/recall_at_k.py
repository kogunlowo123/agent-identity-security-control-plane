"""Recall@K evaluation metric for RAG retrieval."""

from __future__ import annotations


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Compute Recall@K: fraction of relevant docs retrieved in top-K."""
    if not relevant_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / len(relevant_ids)


def mean_recall_at_k(results: list[tuple[list[str], set[str]]], k: int) -> float:
    """Average Recall@K across multiple queries."""
    if not results:
        return 0.0
    return sum(recall_at_k(r, rel, k) for r, rel in results) / len(results)


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) < 2:
        print("Usage: python recall_at_k.py <results.json>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        data = json.load(f)
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    pairs = [(item["retrieved"], set(item["relevant"])) for item in data]
    score = mean_recall_at_k(pairs, k)
    print(f"Mean Recall@{k}: {score:.4f}")
