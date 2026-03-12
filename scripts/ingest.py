"""
scripts/ingest.py
Run this ONCE to populate all 4 Qdrant collections.

Usage:
    python scripts/ingest.py
"""

import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, PayloadSchemaType
)
import requests
from tqdm import tqdm
from config.settings import (
    QDRANT_URL,
    QDRANT_API_KEY,
    COLLECTIONS,
    VECTOR_SIZE,
    EMBED_MODEL,
    DASHSCOPE_BASE_URL,
    DASHSCOPE_API_KEY,
)

# ── Setup ────────────────────────────────────────────────────────────────────
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def embed_text(text: str) -> list[float]:
    response = requests.post(
        f"{DASHSCOPE_BASE_URL}/embeddings",
        headers={
            "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": EMBED_MODEL,
            "input": text,
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return data["data"][0]["embedding"]

MATERIAL_KNOWLEDGE = [
    {
        "material": "merino wool",
        "properties": "Soft, temperature-regulating, moisture-wicking. Warm in cold but breathable in mild weather. Fine fiber means less itch than regular wool.",
        "skin_notes": "Generally hypoallergenic. Safe for most sensitive skin and mild eczema. Rare allergy to lanolin possible.",
        "warmth_range": "mild to cold (-5 to 15°C with layering)"
    },
    {
        "material": "duck down",
        "properties": "Excellent warmth-to-weight ratio. Very compressible. Loses insulation when wet.",
        "skin_notes": "Outer shell is typically polyester/nylon — no direct skin contact. Rare feather allergy possible.",
        "warmth_range": "cold to extreme cold. 400g fill: -5°C. 600g fill: -15°C. 800g+: -20°C and below"
    },
    {
        "material": "cotton",
        "properties": "Soft and breathable. Absorbs moisture but dries slowly. Not warm when wet.",
        "skin_notes": "Most skin-friendly fabric. Excellent for sensitive skin and allergies.",
        "warmth_range": "spring/autumn, room temperature. Not suitable for cold outdoor wear."
    },
    {
        "material": "polyester",
        "properties": "Durable, quick-drying, affordable. Less breathable than natural fibers. Retains shape well.",
        "skin_notes": "May cause irritation for very sensitive skin due to synthetic fibers. Can trap heat and sweat.",
        "warmth_range": "depends on weave. Fleece polyester: mild to cold."
    },
    {
        "material": "memory foam",
        "properties": "Conforms to body shape under pressure. Good shock absorption. Compresses over time with heavy use.",
        "skin_notes": "Generally non-irritating. Some low-quality foams may off-gas initially.",
        "warmth_range": "N/A (footwear/bedding material)"
    }
]


def create_collections():
    """Create all 4 Qdrant collections if they don't exist."""
    for name in COLLECTIONS.values():
        existing = [c.name for c in client.get_collections().collections]
        if name in existing:
            print(f"  Collection '{name}' already exists, skipping.")
            continue
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
        )
        print(f"  Created collection: {name}")

    # 建完 collection 后加 payload 索引
    for field in ["product_id", "sentiment"]:
        try:
            client.create_payload_index(
                collection_name=COLLECTIONS["reviews"],
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD
            )
            print(f"  Created index: reviews.{field}")
        except Exception:
            pass  # 已存在则跳过

    # sizing collection 索引
    try:
        client.create_payload_index(
            collection_name=COLLECTIONS["sizing"],
            field_name="product_id",
            field_schema=PayloadSchemaType.KEYWORD
        )
        print(f"  Created index: sizing.product_id")
    except Exception:
        pass


def ingest_products(products):
    """
    Ingest into two collections:
    - product_visual_desc: one entry per product (description text)
    - reviews_chunks: one entry per review sentence
    """
    visual_points = []
    review_points = []
    review_id = 0

    for product in tqdm(products, desc="Processing products"):
        # ── Collection 1: Visual descriptions ──
        # In production, this would call vision model on the image.
        # For now we use the text description as a stand-in.
        # See agent/tools.py for the real vision call.
        visual_text = f"{product['name']}: {product['description']}"
        visual_points.append(PointStruct(
            id=hash(product['id']) % (2**31),  # Qdrant needs int or UUID
            vector=embed_text(visual_text),
            payload={
                "product_id": product['id'],
                "name": product['name'],
                "category": product['category'],
                "brand": product['brand'],
                "price": product['price'],
                "description": visual_text,
                "image_url": product['image_url'],
            }
        ))

        # ── Collection 2: Review chunks ──
        for review in product.get('reviews', []):
            review_points.append(PointStruct(
                id=review_id,
                vector=embed_text(review['text']),
                payload={
                    "product_id": product['id'],
                    "text": review['text'],
                    "rating": review['rating'],
                    "reviewer_height": review.get('reviewer_height'),
                    # Simple sentiment from rating
                    "sentiment": "positive" if review['rating'] >= 4 else
                                 "negative" if review['rating'] <= 2 else "neutral",
                }
            ))
            review_id += 1

    client.upsert(collection_name=COLLECTIONS["visual"], points=visual_points)
    print(f"  Ingested {len(visual_points)} products into visual collection")

    client.upsert(collection_name=COLLECTIONS["reviews"], points=review_points)
    print(f"  Ingested {len(review_points)} review chunks into reviews collection")


def ingest_knowledge():
    """Ingest material knowledge base."""
    points = []
    for i, item in enumerate(MATERIAL_KNOWLEDGE):
        text = f"{item['material']}: {item['properties']} {item['skin_notes']} Warmth: {item['warmth_range']}"
        points.append(PointStruct(
            id=i,
            vector=embed_text(text),
            payload=item
        ))
    client.upsert(collection_name=COLLECTIONS["knowledge"], points=points)
    print(f"  Ingested {len(points)} material knowledge entries")


def ingest_sizing(products):
    """Ingest sizing guides from product data."""
    points = []
    point_id = 0
    for product in products:
        if 'sizing' not in product:
            continue
        for size_label, size_range in product['sizing'].items():
            text = f"{product['brand']} {product['name']} size {size_label}: fits {size_range}"
            points.append(PointStruct(
                id=point_id,
                vector=embed_text(text),
                payload={
                    "product_id": product['id'],
                    "brand": product['brand'],
                    "category": product['category'],
                    "size_label": size_label,
                    "size_range": size_range,
                }
            ))
            point_id += 1
    client.upsert(collection_name=COLLECTIONS["sizing"], points=points)
    print(f"  Ingested {len(points)} sizing guide entries")


if __name__ == "__main__":
    print("=== ShopSense Data Ingestion ===\n")

    print("Step 1: Creating Qdrant collections...")
    create_collections()

    print("\nStep 2: Loading product data...")
    with open("data/sample_products.json") as f:
        products = json.load(f)
    print(f"  Loaded {len(products)} products")

    print("\nStep 3: Ingesting products and reviews...")
    ingest_products(products)

    print("\nStep 4: Ingesting material knowledge...")
    ingest_knowledge()

    print("\nStep 5: Ingesting sizing guides...")
    ingest_sizing(products)

    print("\n✅ All done! Qdrant is ready.")
