"""CI gate for RAG evaluation — fails if metrics drop below thresholds."""

from __future__ import annotations

import json
import sys
from pathlib import Path

THRESHOLDS = {
    "recall_at_10": 0.70,
    "mrr": 0.60,
    "faithfulness": 0.75,
    "citation_f1": 0.70,
}


def load_results(results_dir: Path) -> dict:
    combined: dict = {}
    for metrics_file in results_dir.glob("*.json"):
        with open(metrics_file) as f:
            data = json.load(f)
        combined.update(data)
    return combined


def gate(results: dict) -> list[str]:
    failures: list[str] = []
    for metric, threshold in THRESHOLDS.items():
        value = results.get(metric)
        if value is None:
            failures.append(f"MISSING metric: {metric}")
        elif value < threshold:
            failures.append(
                f"BELOW THRESHOLD: {metric} = {value:.4f} (required >= {threshold:.4f})"
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: python ci_gate.py <results_dir>", file=sys.stderr)
        return 2

    results_dir = Path(argv[0])
    if not results_dir.exists():
        print(f"ERROR: Results directory not found: {results_dir}", file=sys.stderr)
        return 2

    results = load_results(results_dir)
    if not results:
        print("ERROR: No results files found", file=sys.stderr)
        return 2

    failures = gate(results)
    if failures:
        print("EVAL CI GATE FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("EVAL CI GATE PASSED:")
    for metric, value in results.items():
        threshold = THRESHOLDS.get(metric)
        if threshold is not None:
            print(f"  {metric}: {value:.4f} >= {threshold:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
