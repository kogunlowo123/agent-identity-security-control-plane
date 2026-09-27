"""HTML document loader using BeautifulSoup."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_html(path: str | Path) -> list[dict]:
    """Load text content from an HTML file. Returns list of {text, metadata}."""
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise ImportError("beautifulsoup4 required: pip install beautifulsoup4") from exc

    path = Path(path)
    with open(path, encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    title = soup.title.string if soup.title else path.stem

    return [{
        "text": text,
        "metadata": {
            "source": str(path),
            "mime_type": "text/html",
            "title": title,
        },
    }]
