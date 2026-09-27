"""Input screening guardrail for agent runtime."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

INJECTION_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"(?i)(ignore|forget|disregard).{0,50}(instruction|system|prompt)",
        "prompt_injection",
        "high",
    ),
    (r"(?i)(jailbreak|dan mode|ignore previous)", "jailbreak_attempt", "critical"),
    (r"(?i)(drop table|delete from|truncate|exec\s*\()", "sql_injection", "high"),
    (r"(?i)(<script|javascript:|onerror=|onload=)", "xss_attempt", "high"),
]

MAX_INPUT_LENGTH = 8192


@dataclass
class ScreeningResult:
    allowed: bool
    violations: list[dict]
    sanitized_input: str


def screen_input(user_input: str) -> ScreeningResult:
    violations: list[dict] = []

    if len(user_input) > MAX_INPUT_LENGTH:
        violations.append(
            {
                "label": "input_too_long",
                "severity": "medium",
                "detail": f"Input length {len(user_input)} exceeds max {MAX_INPUT_LENGTH}",
            }
        )
        user_input = user_input[:MAX_INPUT_LENGTH]

    for pattern, label, severity in INJECTION_PATTERNS:
        match = re.search(pattern, user_input)
        if match:
            violations.append(
                {
                    "label": label,
                    "severity": severity,
                    "match": match.group(0)[:64],
                }
            )
            logger.warning("Input screening violation: %s severity=%s", label, severity)

    critical = any(v["severity"] == "critical" for v in violations)
    high_count = sum(1 for v in violations if v["severity"] == "high")

    allowed = not critical and high_count < 2

    return ScreeningResult(
        allowed=allowed,
        violations=violations,
        sanitized_input=user_input,
    )
