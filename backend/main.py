"""
backend/main.py

FastAPI entry point for ShopSense.

Run:
    (from the repository root)
    uvicorn backend.main:app --reload --port 8000
"""

import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from config.settings import QDRANT_COLLECTIONS, get_qdrant_client
from agent.review_insights import answer_question, render_highlights, search_products


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="ShopSense API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_qdrant():
    return get_qdrant_client()


_catalogue: dict = {}


def catalogue() -> dict:
    """All product payloads by ASIN, read from Qdrant once (300 items)."""
    if not _catalogue:
        points, _ = get_qdrant().scroll(
            collection_name=QDRANT_COLLECTIONS["products"],
            limit=10_000,
            with_payload=True,
            with_vectors=False,
        )
        _catalogue.update({p.payload["asin"]: p.payload for p in points})
    return _catalogue


def product_or_404(asin: str) -> dict:
    product = catalogue().get(asin)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# ── Pydantic Models ───────────────────────────────────────────────────────────

Lang = Literal["zh", "en"]


class AskRequest(BaseModel):
    asin: str
    question: str
    lang: Lang = "zh"


class SearchRequest(BaseModel):
    query: str
    lang: Lang = "zh"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/products")
def get_products():
    return [
        {k: p[k] for k in ("asin", "name", "brand", "price", "image_url", "category",
                           "gender", "rating", "review_count")}
        for p in sorted(catalogue().values(), key=lambda p: p["name"])
    ]


@app.get("/api/products/{asin}")
def get_product(asin: str, lang: Lang = "zh"):
    """
    Product details in `lang`: the review highlights (feature 1) and what the
    shoe looks like, described from its photo (scripts/generate_visual_descriptions.py).
    """
    product = product_or_404(asin)
    details = {k: v for k, v in product.items() if k not in ("highlights", "appearance")}
    return {
        **details,
        "highlights": render_highlights(product["highlights"], lang),
        "appearance": product["appearance"][lang],
    }


@app.post("/api/ask")
def ask(req: AskRequest):
    """Answer a question from this product's reviews only (feature 2)."""
    return answer_question(product_or_404(req.asin), req.question, req.lang)


@app.post("/api/search")
def search(req: SearchRequest):
    """Recommend products whose reviews match a need (feature 3)."""
    return search_products(req.query, catalogue(), req.lang)
