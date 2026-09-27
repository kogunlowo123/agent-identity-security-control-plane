"""Citation accuracy evaluation — checks that cited chunk IDs exist in the retrieved set."""

from __future__ import annotations

import re


def extract_citations(text: str) -> list[str]:
    return re.findall(r"\[([^\]]+)\]", text)


def citation_precision(generated: str, valid_ids: set[str]) -> float:
    cited = extract_citations(generated)
    if not cited:
        return 1.0
    valid_cited = sum(1 for c in cited if c in valid_ids)
    return valid_cited / len(cited)


def citation_recall(generated: str, required_ids: set[str]) -> float:
    if not required_ids:
        return 1.0
    cited = set(extract_citations(generated))
    found = cited & required_ids
    return len(found) / len(required_ids)


def batch_citation_accuracy(records: list[dict]) -> dict:
    """
    records: list of {"generated": str, "valid_ids": list[str], "required_ids": list[str]}
    """
    precisions = []
    recalls = []
    for r in records:
        precisions.append(citation_precision(r["generated"], set(r.get("valid_ids", []))))
        recalls.append(citation_recall(r["generated"], set(r.get("required_ids", []))))
    mean_p = sum(precisions) / len(precisions) if precisions else 0.0
    mean_r = sum(recalls) / len(recalls) if recalls else 0.0
    f1 = 2 * mean_p * mean_r / (mean_p + mean_r) if (mean_p + mean_r) > 0 else 0.0
    return {"precision": mean_p, "recall": mean_r, "f1": f1}


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) < 2:
        print("Usage: python citation_accuracy.py <records.json>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        records = json.load(f)
    result = batch_citation_accuracy(records)
    print(f"Citation Precision: {result['precision']:.4f}")
    print(f"Citation Recall:    {result['recall']:.4f}")
    print(f"Citation F1:        {result['f1']:.4f}")
