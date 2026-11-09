"""core/embeddings.py

Embedding service using a local sentence-transformers model (no API key).

The default model is multilingual E5, which is trained with asymmetric
prefixes: search text is embedded as "query: …" and stored text as
"passage: …". `embed` is for queries, `embed_batch` for stored documents.
"""

import threading
from typing import List

from sentence_transformers import SentenceTransformer

from config.settings import EMBED_MODEL

_model: SentenceTransformer = None
_model_lock = threading.Lock()


def _get_model() -> SentenceTransformer:
    """
    Load the model once.

    The lock matters because tool calls run in worker threads, so two
    concurrent requests can reach this at the same time on a cold start.
    """
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                print(f"[Embeddings] Loading {EMBED_MODEL} ...")
                _model = SentenceTransformer(EMBED_MODEL)
                print("[Embeddings] Model loaded.")
    return _model


def embed(text: str) -> List[float]:
    """Embed one search query."""
    return _get_model().encode("query: " + text, normalize_embeddings=True).tolist()


def embed_batch(texts: List[str], show_progress: bool = False) -> List[List[float]]:
    """Embed stored documents (reviews, product texts)."""
    vectors = _get_model().encode(
        ["passage: " + t for t in texts],
        normalize_embeddings=True,
        show_progress_bar=show_progress,
        batch_size=64,
    )
    return vectors.tolist()
