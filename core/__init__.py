"""core/__init__.py

Core services for ShopSense.
"""

from core.embeddings import EmbeddingService, embed, embed_batch, get_embedding_service

__all__ = [
    "EmbeddingService",
    "embed",
    "embed_batch",
    "get_embedding_service",
]
