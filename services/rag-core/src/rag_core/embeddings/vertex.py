"""Vertex AI text embedding using textembedding-gecko."""

from __future__ import annotations

import logging
from typing import Any

from rag_core.embeddings.base import BaseEmbedder

logger = logging.getLogger(__name__)

VERTEX_MODEL = "textembedding-gecko@003"
VERTEX_DIMENSIONS = 768


class VertexAIEmbedder(BaseEmbedder):
    DIMENSIONS = VERTEX_DIMENSIONS

    def __init__(self, project_id: str, location: str = "us-central1", model: str = VERTEX_MODEL) -> None:
        self._project_id = project_id
        self._location = location
        self._model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google.cloud import aiplatform
                from vertexai.language_models import TextEmbeddingModel
                aiplatform.init(project=self._project_id, location=self._location)
                self._client = TextEmbeddingModel.from_pretrained(self._model)
            except ImportError as exc:
                raise ImportError("google-cloud-aiplatform required: pip install google-cloud-aiplatform[vertexai]") from exc
        return self._client

    async def embed(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import asyncio
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _encode() -> list[list[float]]:
            embeddings = client.get_embeddings(texts)
            return [e.values for e in embeddings]

        return await loop.run_in_executor(None, _encode)
