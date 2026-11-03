"""
backend/main.py

FastAPI entry point for ShopSense v2.

Run:
    (from the repository root)
    uvicorn backend.main:app --reload --port 8000
"""

import os
import sys
import time

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal

from qdrant_client.models import Filter, FieldCondition, MatchValue

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from config.settings import QDRANT_COLLECTIONS, get_qdrant_client
from agent.react import react_loop, _detect_conflicts, _build_retrieval_summary
from agent.legacy import run_legacy_query
from agent.page import answer_from_page
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

class UserContext(BaseModel):
    height: int | None = None        # cm
    weight: int | None = None        # kg
    temp_target: str | None = None   # e.g. "-10°C"
    skin_sensitive: bool | None = None


class QueryRequest(BaseModel):
    asin: str
    question: str
    history: list[dict] = []
    user_context: UserContext = UserContext()


class ExtensionQueryRequest(BaseModel):
    """What the browser extension scraped off a live product page."""
    asin: str = ""
    title: str = ""
    brand: str | None = None
    price: str | None = None
    description: str = ""
    bullets: list[str] = []
    reviews: list[str] = []
    image_url: str | None = None
    question: str = ""


# ── Routes ────────────────────────────────────────────────────────────────────

Lang = Literal["zh", "en"]


class AskRequest(BaseModel):
    asin: str
    question: str
    lang: Lang = "zh"


class SearchRequest(BaseModel):
    query: str
    lang: Lang = "zh"


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


@app.post("/api/query")
async def query(req: QueryRequest):
    client = get_qdrant()
    start = time.time()

    product_results, _ = client.scroll(
        collection_name=QDRANT_COLLECTIONS["products"],
        scroll_filter=Filter(must=[FieldCondition(key="asin", match=MatchValue(value=req.asin))]),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    if not product_results:
        raise HTTPException(status_code=404, detail="Product not found")
    product = product_results[0].payload

    answer, trace, retrieved = await react_loop(
        question=req.question,
        asin=req.asin,
        product=product,
        history=req.history,
        user_context=req.user_context,
    )

    total_ms = round((time.time() - start) * 1000)

    last_reflection = next(
        (step["reflection"] for step in reversed(trace) if "reflection" in step), None
    )

    return {
        "answer": answer,
        "retrieval_summary": _build_retrieval_summary(trace),
        "reasoning_trace": trace,
        "conflict_detection": _detect_conflicts(retrieved["knowledge"], retrieved["reviews"], product),
        "reflection": last_reflection,
        "timing": {"total_ms": total_ms},
    }


@app.post("/api/query_legacy")
async def query_legacy(req: QueryRequest):
    """Legacy single-pass endpoint preserved for A/B comparison."""
    client = get_qdrant()

    product_results, _ = client.scroll(
        collection_name=QDRANT_COLLECTIONS["products"],
        scroll_filter=Filter(must=[FieldCondition(key="asin", match=MatchValue(value=req.asin))]),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    if not product_results:
        raise HTTPException(status_code=404, detail="Product not found")

    # Attach product payload so run_legacy_query can access it
    req._product = product_results[0].payload

    return await run_legacy_query(req, client)


@app.post("/api/extension_query")
async def extension_query(req: ExtensionQueryRequest):
    """
    Answer from a live product page the browser extension scraped.

    There is no Qdrant lookup here: the product is not in our data set. The
    seller's own copy is compared against the reviews on that same page, so
    the extension gets a real conflict check instead of its offline keyword
    guess. Works with no API key too — it falls back to a plain reading of
    the page rather than failing.
    """
    if not (req.title or req.description or req.reviews):
        raise HTTPException(status_code=400, detail="No page content received")
    return await answer_from_page(req)


@app.get("/api/tools")
async def get_tools():
    return [
        {"name": "review_search", "description": "Semantic search over customer reviews filtered by product"},
        {"name": "knowledge_search", "description": "Search expert fabric and material knowledge base"},
        {"name": "visual_search", "description": "Search visual image descriptions for accessibility"},
    ]
