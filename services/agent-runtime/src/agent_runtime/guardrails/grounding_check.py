"""Grounding check guardrail — ensures LLM output is supported by retrieved context."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

GROUNDING_THRESHOLD = 0.7


@dataclass
class GroundingResult:
    score: float
    is_grounded: bool
    ungrounded_claims: list[str]


def _extract_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]


def _sentence_in_context(sentence: str, context_chunks: list[str]) -> bool:
    sentence_lower = sentence.lower()
    words = set(re.findall(r"\b\w{4,}\b", sentence_lower))
    if not words:
        return True
    for chunk in context_chunks:
        chunk_lower = chunk.lower()
        overlap = sum(1 for w in words if w in chunk_lower)
        if overlap / len(words) >= 0.4:
            return True
    return False


def check_grounding(
    generated_text: str,
    context_chunks: list[str],
    threshold: float = GROUNDING_THRESHOLD,
) -> GroundingResult:
    sentences = _extract_sentences(generated_text)
    if not sentences:
        return GroundingResult(score=1.0, is_grounded=True, ungrounded_claims=[])

    ungrounded: list[str] = []
    for sentence in sentences:
        if not _sentence_in_context(sentence, context_chunks):
            ungrounded.append(sentence)

    score = 1.0 - (len(ungrounded) / len(sentences))
    is_grounded = score >= threshold

    if not is_grounded:
        logger.warning(
            "Grounding check failed: score=%.2f threshold=%.2f ungrounded=%d/%d",
            score,
            threshold,
            len(ungrounded),
            len(sentences),
        )

    return GroundingResult(score=score, is_grounded=is_grounded, ungrounded_claims=ungrounded)
