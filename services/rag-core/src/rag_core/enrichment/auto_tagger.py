"""Automatic keyword tagging for RAG chunks."""

from __future__ import annotations

import re
from typing import Any

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "spiffe": ["spiffe", "svid", "spire", "workload identity", "trust domain"],
    "jwt": ["jwt", "json web token", "bearer token", "jti", "claims"],
    "opa": ["opa", "open policy agent", "rego", "policy"],
    "delegation": ["delegation", "delegate", "chain", "depth"],
    "revocation": ["revocation", "revoke", "blacklist", "crl"],
    "kubernetes": ["kubernetes", "k8s", "pod", "namespace", "service account"],
    "iam": ["iam", "identity", "authentication", "authorization", "access control"],
}


def auto_tag(chunk: dict[str, Any]) -> dict[str, Any]:
    text = chunk.get("text", "").lower()
    tags: list[str] = []
    for tag, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            tags.append(tag)
    existing = chunk["metadata"].get("tags", [])
    chunk["metadata"]["tags"] = list(set(existing + tags))
    return chunk
