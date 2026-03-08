"""
agent/tools.py
Four tools the Agent can call:
  1. visual_analysis  — describe a product image using LLaVA
  2. search_knowledge — query material_knowledge collection
  3. search_reviews   — query reviews_chunks collection
  4. search_sizing    — query sizing_guide collection
"""

import requests
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
from huggingface_hub import InferenceClient

from config.settings import (
    QDRANT_URL,
    QDRANT_API_KEY,
    COLLECTIONS,
    HF_API_KEY,
    QWEN_MODEL,
    EMBED_MODEL,
    TOP_K,
)

# Singletons — initialised once and reused
_qdrant = None
_embedder = None


def get_qdrant():
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    return _qdrant


def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


# ── Tool 1: Visual Analysis ───────────────────────────────────────────────────


def visual_analysis(image_url: str, question: str = None) -> dict:
    prompt = question or (
        "Describe this product image in detail for a visually impaired shopper. "
        "Include: exact color with shade references, material texture using touch "
        "analogies, visible dimensions with everyday size comparisons, design "
        "details like pockets/zippers/patterns, and how it looks when worn or used. "
        "Be specific. Avoid vague words like 'nice' or 'good'."
    )

    if not image_url or image_url == "placeholder":
        return {
            "description": "No image available. Using product description instead.",
            "source": "placeholder",
        }

    try:
        client = InferenceClient(
            api_key=HF_API_KEY,
        )
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            max_tokens=300,
        )
        description = response.choices[0].message.content.strip()
        return {"description": description, "source": "llama-vision"}

    except Exception as e:
        print(f"[visual_analysis] API call failed: {e}. Using placeholder.")
        return {
            "description": "Image analysis unavailable. Using product description.",
            "source": "placeholder",
        }


# ── Tool 2: Knowledge Retrieval ───────────────────────────────────────────────


def search_knowledge(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Semantic search over material_knowledge collection.
    No product filter — knowledge is global.

    Returns list of dicts with 'text' and 'score'.
    """
    embedder = get_embedder()
    vector = embedder.encode(query).tolist()

    results = (
        get_qdrant()
        .query_points(
            collection_name=COLLECTIONS["knowledge"],
            query=vector,
            limit=top_k,
            with_payload=True,
        )
        .points
    )

    return [
        {
            "material": r.payload.get("material", ""),
            "text": f"{r.payload.get('properties', '')} {r.payload.get('skin_notes', '')} "
            f"Warmth: {r.payload.get('warmth_range', '')}",
            "score": r.score,
        }
        for r in results
    ]


# ── Tool 3: Review Search ─────────────────────────────────────────────────────


def search_reviews(
    query: str,
    product_id: str,
    sentiment: str = None,  # "positive" | "negative" | "neutral" | None
    reviewer_height_min: int = None,
    reviewer_height_max: int = None,
    top_k: int = TOP_K,
) -> list[dict]:
    """
    Semantic search over reviews_chunks, filtered to a specific product.
    Optional filters: sentiment, reviewer height range.
    """
    embedder = get_embedder()
    vector = embedder.encode(query).tolist()

    # Build Qdrant filter
    conditions = [FieldCondition(key="product_id", match=MatchValue(value=product_id))]

    if sentiment:
        conditions.append(
            FieldCondition(key="sentiment", match=MatchValue(value=sentiment))
        )

    query_filter = Filter(must=conditions)

    results = (
        get_qdrant()
        .query_points(
            collection_name=COLLECTIONS["reviews"],
            query=vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        .points
    )

    # Post-filter by height if specified (Qdrant range filter also possible)
    filtered = []
    for r in results:
        height = r.payload.get("reviewer_height")
        if reviewer_height_min and height and height < reviewer_height_min:
            continue
        if reviewer_height_max and height and height > reviewer_height_max:
            continue
        filtered.append(
            {
                "text": r.payload.get("text", ""),
                "rating": r.payload.get("rating"),
                "sentiment": r.payload.get("sentiment"),
                "reviewer_height": height,
                "score": r.score,
            }
        )

    return filtered


# ── Tool 4: Sizing Search ─────────────────────────────────────────────────────


def search_sizing(
    product_id: str, height: int = None, weight: int = None, top_k: int = 3
) -> list[dict]:
    """
    Search sizing guide for a specific product.
    If height/weight provided, query with those as context.
    """
    embedder = get_embedder()
    query = (
        f"size for height {height}cm weight {weight}kg" if height else "sizing guide"
    )
    vector = embedder.encode(query).tolist()

    query_filter = Filter(
        must=[FieldCondition(key="product_id", match=MatchValue(value=product_id))]
    )

    results = (
        get_qdrant()
        .query_points(
            collection_name=COLLECTIONS["sizing"],
            query=vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        .points
    )

    return [
        {
            "size_label": r.payload.get("size_label"),
            "size_range": r.payload.get("size_range"),
            "score": r.score,
        }
        for r in results
    ]
