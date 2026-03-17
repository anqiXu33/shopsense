"""
backend/main.py

FastAPI entry point for ShopSense v2.

Run:
    cd backend
    uvicorn main:app --reload --port 8000
"""

import asyncio
import os
import sys
import time

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import requests as req_lib
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from config.settings import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTIONS
from agent.react import react_loop, _detect_conflicts, _build_retrieval_summary
from agent.legacy import run_legacy_query


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="ShopSense API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_qdrant: QdrantClient = None


def get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    return _qdrant


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


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/products")
async def get_products():
    client = get_qdrant()
    results, _ = client.scroll(
        collection_name=QDRANT_COLLECTIONS["products"],
        limit=100,
        with_payload=True,
        with_vectors=False,
    )
    return [
        {
            "asin": p.payload["asin"],
            "name": p.payload["name"],
            "brand": p.payload["brand"],
            "price": p.payload["price"],
            "image_url": p.payload.get("image_url"),
            "category": p.payload["category"],
            "rating": p.payload["rating"],
            "review_count": p.payload["review_count"],
        }
        for p in results
    ]


@app.get("/api/products/{asin}")
async def get_product(asin: str):
    client = get_qdrant()
    results, _ = client.scroll(
        collection_name=QDRANT_COLLECTIONS["products"],
        scroll_filter=Filter(must=[FieldCondition(key="asin", match=MatchValue(value=asin))]),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    if not results:
        raise HTTPException(status_code=404, detail="Product not found")
    return results[0].payload


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
        "conflict_detection": _detect_conflicts(retrieved["knowledge"], retrieved["reviews"]),
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


@app.get("/api/tools")
async def get_tools():
    return [
        {"name": "review_search", "description": "Semantic search over customer reviews filtered by product"},
        {"name": "knowledge_search", "description": "Search expert fabric and material knowledge base"},
        {"name": "visual_search", "description": "Search visual image descriptions for accessibility"},
    ]


@app.get("/api/tts")
async def tts_image(asin: str):
    """Return a spoken description of the product image, including product metadata."""
    client = get_qdrant()

    visual_results, product_results = await asyncio.gather(
        asyncio.to_thread(
            client.scroll,
            collection_name=QDRANT_COLLECTIONS["visual_semantic"],
            scroll_filter=Filter(must=[FieldCondition(key="asin", match=MatchValue(value=asin))]),
            limit=1,
            with_payload=True,
            with_vectors=False,
        ),
        asyncio.to_thread(
            client.scroll,
            collection_name=QDRANT_COLLECTIONS["products"],
            scroll_filter=Filter(must=[FieldCondition(key="asin", match=MatchValue(value=asin))]),
            limit=1,
            with_payload=True,
            with_vectors=False,
        ),
    )

    visual_points, _ = visual_results
    product_points, _ = product_results

    if not visual_points:
        return {"answer": "No visual description available for this product."}

    description = visual_points[0].payload["text"]

    product_context = ""
    if product_points:
        p = product_points[0].payload
        attrs = p.get("attributes", {})
        product_context = (
            f"Product name: {p['name']}\n"
            f"Brand: {p['brand']}\n"
            f"Price: CHF {p['price']}\n"
            f"Material: {attrs.get('material', 'not specified')}\n"
            f"Color: {attrs.get('color', 'not specified')}\n"
        )

    base_url = os.getenv("DASHSCOPE_BASE_URL", "https://api.groq.com/openai/v1")
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("HF_API_KEY")
    model = os.getenv("TEXT_MODEL", "llama-3.3-70b-versatile")

    user_prompt = (
        f"{product_context}\n"
        f"What the image actually shows:\n{description}\n\n"
        "Introduce this product by name and brand. Then describe its appearance based on "
        "what is actually visible in the image — color, shape, texture, closures, and any notable details. "
        "If the image color differs from the listed color, describe what you see in the image. "
        "Write in a warm, natural tone for someone who cannot see the image."
    )

    try:
        resp = req_lib.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are ShopSense, an accessibility assistant that describes product images for visually impaired shoppers. Always base your description on what the image actually shows, not on the listed product attributes. Be clear, warm, and concise (under 80 words)."},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 300,
                "temperature": 0.4,
            },
            timeout=30,
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        answer = description

    return {"answer": answer}


@app.get("/api/tts/speech")
async def tts_speech(text: str):
    """Convert text to speech. Returns audio/mpeg stream.

    Provider priority (first available wins):
      1. OpenAI TTS (tts-1-hd, nova)  — set OPENAI_API_KEY
      2. DashScope CosyVoice           — set DASHSCOPE_API_KEY +
                                         DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/...
    Falls back to 404 so the frontend can use browser TTS.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        def _openai_stream():
            r = req_lib.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={"model": "tts-1-hd", "voice": "nova", "input": text},
                stream=True,
                timeout=30,
            )
            r.raise_for_status()
            yield from r.iter_content(chunk_size=4096)
        return StreamingResponse(_openai_stream(), media_type="audio/mpeg")

    ds_key = os.getenv("DASHSCOPE_API_KEY")
    ds_base = os.getenv("DASHSCOPE_BASE_URL", "")
    if ds_key and "dashscope.aliyuncs.com" in ds_base:
        try:
            resp = await asyncio.to_thread(
                req_lib.post,
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-to-speech/call",
                headers={
                    "Authorization": f"Bearer {ds_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-SSE": "disable",
                },
                json={
                    "model": "cosyvoice-v1",
                    "input": {"text": text},
                    "parameters": {"voice": "longxiaochun", "format": "mp3", "sample_rate": 22050},
                },
                timeout=30,
            )
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "")
            if "audio" in ct:
                return StreamingResponse(iter([resp.content]), media_type="audio/mpeg")
            import base64
            audio_b64 = resp.json().get("output", {}).get("audio", "")
            if audio_b64:
                return StreamingResponse(iter([base64.b64decode(audio_b64)]), media_type="audio/mpeg")
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="TTS not configured")
