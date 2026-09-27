"""Local BGE embedder using sentence-transformers (BAAI/bge-large-en-v1.5)."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from rag_core.embeddings.base import BaseEmbedder

logger = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-large-en-v1.5"
BGE_DIMENSIONS = 1024


class LocalBGEEmbedder(BaseEmbedder):
    DIMENSIONS = BGE_DIMENSIONS

    def __init__(self, model_name: str = MODEL_NAME, device: str = "cpu") -> None:
        self._model_name = model_name
        self._device = device
        self._model = None
        self._executor = ThreadPoolExecutor(max_workers=2)

    def _load_model(self) -> None:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name, device=self._device)
                logger.info("Loaded embedding model: %s", self._model_name)
            except ImportError as exc:
                raise ImportError("sentence-transformers required: pip install sentence-transformers") from exc

    def _encode_sync(self, texts: list[str]) -> list[list[float]]:
        self._load_model()
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    async def embed(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self._encode_sync, texts)
