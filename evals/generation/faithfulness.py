"""Faithfulness evaluation — measures how well generated text is grounded in context."""

from __future__ import annotations

import re


def sentence_overlap_score(generated: str, context: str) -> float:
    """Compute fraction of generated sentences supported by context."""
    def sentences(text: str) -> list[str]:
        return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 15]

    def supported(sentence: str, context_lower: str) -> bool:
        words = set(re.findall(r"\b\w{4,}\b", sentence.lower()))
        if not words:
            return True
        overlap = sum(1 for w in words if w in context_lower)
        return (overlap / len(words)) >= 0.35

    gen_sents = sentences(generated)
    if not gen_sents:
        return 1.0

    context_lower = context.lower()
    supported_count = sum(1 for s in gen_sents if supported(s, context_lower))
    return supported_count / len(gen_sents)


def batch_faithfulness(
    records: list[dict],
) -> dict:
    """
    records: list of {"generated": str, "context": str}
    Returns: {"mean": float, "scores": list[float]}
    """
    scores = [sentence_overlap_score(r["generated"], r["context"]) for r in records]
    mean = sum(scores) / len(scores) if scores else 0.0
    return {"mean": mean, "scores": scores}


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) < 2:
        print("Usage: python faithfulness.py <records.json>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        records = json.load(f)
    result = batch_faithfulness(records)
    print(f"Mean Faithfulness: {result['mean']:.4f}")
