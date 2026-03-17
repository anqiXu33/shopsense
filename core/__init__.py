"""core/__init__.py

Core services for ShopSense.
"""

from core.embeddings import embed, embed_batch

__all__ = [
    "embed",
    "embed_batch",
]
