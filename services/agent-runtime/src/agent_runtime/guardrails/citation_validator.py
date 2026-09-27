"""Citation validator guardrail — verifies citations reference actual retrieved chunks."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CitationValidationResult:
    valid: bool
    valid_count: int
    invalid_count: int
    missing_ids: list[str]


def _extract_citation_ids(text: str) -> list[str]:
    return re.findall(r"\[([^\]]+)\]", text)


def validate_citations(
    generated_text: str,
    chunk_ids: list[str],
) -> CitationValidationResult:
    cited_ids = _extract_citation_ids(generated_text)
    chunk_id_set = set(chunk_ids)

    valid = 0
    invalid = 0
    missing: list[str] = []

    for cid in cited_ids:
        if cid in chunk_id_set:
            valid += 1
        else:
            invalid += 1
            missing.append(cid)

    if missing:
        logger.warning("Invalid citations found: %s", missing)

    return CitationValidationResult(
        valid=invalid == 0 and valid > 0,
        valid_count=valid,
        invalid_count=invalid,
        missing_ids=missing,
    )
