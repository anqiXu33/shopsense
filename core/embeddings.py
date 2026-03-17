"""core/embeddings.py

Embedding service using local sentence-transformers model.
No API key required.
"""

from typing import List
from sentence_transformers import SentenceTransformer

_model: SentenceTransformer = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print("[Embeddings] Loading all-MiniLM-L6-v2 model...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[Embeddings] Model loaded.")
    return _model


def embed(text: str) -> List[float]:
    """Generate embedding for a single text."""
    if not text or not text.strip():
        return [0.0] * 384
    model = _get_model()
    return model.encode(text, normalize_embeddings=True).tolist()


def embed_batch(texts: List[str], show_progress: bool = False) -> List[List[float]]:
    """Generate embeddings for multiple texts."""
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=show_progress)
    return vectors.tolist()
