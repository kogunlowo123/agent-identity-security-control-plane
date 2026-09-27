"""PII detection and tagging for RAG chunks."""

from __future__ import annotations

import re
from typing import Any

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_RE = re.compile(r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def detect_pii(text: str) -> list[dict[str, str]]:
    findings = []
    for match in EMAIL_RE.finditer(text):
        findings.append({"type": "EMAIL_ADDRESS", "value": match.group(0), "start": str(match.start()), "end": str(match.end())})
    for match in PHONE_RE.finditer(text):
        findings.append({"type": "PHONE_NUMBER", "value": match.group(0), "start": str(match.start()), "end": str(match.end())})
    for match in SSN_RE.finditer(text):
        findings.append({"type": "US_SSN", "value": "***-**-****", "start": str(match.start()), "end": str(match.end())})
    return findings


def tag_pii(chunk: dict[str, Any]) -> dict[str, Any]:
    text = chunk.get("text", "")
    findings = detect_pii(text)
    if findings:
        chunk["metadata"]["pii_detected"] = True
        chunk["metadata"]["pii_types"] = list({f["type"] for f in findings})
    else:
        chunk["metadata"]["pii_detected"] = False
    return chunk
