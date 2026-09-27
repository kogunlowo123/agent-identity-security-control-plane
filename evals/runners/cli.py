"""CLI for running RAG evaluations."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def run_retrieval_eval(data_path: Path, k: int = 10) -> dict:
    from evals.retrieval.recall_at_k import mean_recall_at_k
    from evals.retrieval.mrr import mean_reciprocal_rank

    with open(data_path) as f:
        data = json.load(f)
    pairs = [(item["retrieved"], set(item["relevant"])) for item in data]
    return {
        f"recall_at_{k}": mean_recall_at_k(pairs, k),
        "mrr": mean_reciprocal_rank(pairs),
    }


def run_generation_eval(data_path: Path) -> dict:
    from evals.generation.faithfulness import batch_faithfulness
    from evals.generation.citation_accuracy import batch_citation_accuracy

    with open(data_path) as f:
        records = json.load(f)

    faith = batch_faithfulness(records)
    cite = batch_citation_accuracy(records)
    return {
        "faithfulness": faith["mean"],
        "citation_f1": cite["f1"],
        "citation_precision": cite["precision"],
        "citation_recall": cite["recall"],
    }


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if len(argv) < 2:
        print("Usage: python cli.py <retrieval|generation|all> <data_path> [output_dir]")
        return 2

    mode, data_path_str = argv[0], argv[1]
    data_path = Path(data_path_str)
    output_dir = Path(argv[2]) if len(argv) > 2 else Path("evals/results")
    output_dir.mkdir(parents=True, exist_ok=True)

    results: dict = {}
    if mode in ("retrieval", "all"):
        results.update(run_retrieval_eval(data_path))
    if mode in ("generation", "all"):
        results.update(run_generation_eval(data_path))

    output_file = output_dir / f"{mode}_metrics.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results written to {output_file}")

    for k, v in results.items():
        print(f"  {k}: {v:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
