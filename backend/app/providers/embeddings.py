"""Embeddings Provider Adapter (Local Multilingual SentenceTransformers / OpenAI)

Implements BaseEmbeddingsProvider for semantic ranking and pgvector market map storage.
"""
from typing import List, Optional
from app.config.settings import settings
from app.providers.base import (
    BaseEmbeddingsProvider,
    ProviderError,
)


class EmbeddingsAdapter(BaseEmbeddingsProvider):
    """Adapter for local and external embedding generation."""

    def __init__(self, provider_type: Optional[str] = None):
        self.provider_type = provider_type or settings.EMBEDDING_PROVIDER
        self.model_name = settings.EMBEDDING_MODEL_NAME

    async def embed_text(self, text: str) -> List[float]:
        """Stage 1 interface stub. Full implementation in Stage 4."""
        raise NotImplementedError("EmbeddingsAdapter.embed_text will be implemented in Stage 4")

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Stage 1 interface stub. Full implementation in Stage 4."""
        raise NotImplementedError("EmbeddingsAdapter.embed_batch will be implemented in Stage 4")
