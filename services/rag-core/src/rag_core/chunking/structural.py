"""Structural chunker — splits on Markdown headings."""

from __future__ import annotations

import re
import uuid
from typing import Any

from rag_core.chunking.base import BaseChunker

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class StructuralChunker(BaseChunker):
    """Split text at Markdown section headings."""

    def chunk(self, text: str, metadata: dict[str, Any]) -> list[dict]:
        positions = [(m.start(), m.group(2)) for m in HEADING_RE.finditer(text)]
        if not positions:
            return [{"chunk_id": str(uuid.uuid4()), "text": text.strip(), "metadata": {**metadata, "chunk_index": 0}}]

        sections: list[tuple[str, str]] = []
        for i, (start, heading) in enumerate(positions):
            end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
            section_text = text[start:end].strip()
            sections.append((heading, section_text))

        return [
            {
                "chunk_id": str(uuid.uuid4()),
                "text": section_text,
                "metadata": {**metadata, "section": heading, "chunk_index": i},
            }
            for i, (heading, section_text) in enumerate(sections) if section_text
        ]
