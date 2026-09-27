"""PDF document loader using pypdf."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_pdf(path: str | Path) -> list[dict]:
    """Load pages from a PDF file. Returns list of {page_num, text, metadata}."""
    try:
        import pypdf
    except ImportError as exc:
        raise ImportError("pypdf required: pip install pypdf") from exc

    path = Path(path)
    pages = []
    with open(path, "rb") as f:
        reader = pypdf.PdfReader(f)
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages.append({
                "page_num": i + 1,
                "text": text.strip(),
                "metadata": {
                    "source": str(path),
                    "mime_type": "application/pdf",
                    "page": i + 1,
                    "total_pages": len(reader.pages),
                },
            })
    logger.info("Loaded %d pages from %s", len(pages), path)
    return pages
