"""scripts/ingest_v2.py

Data ingestion script for new Qdrant collections.
Imports products, reviews, knowledge, and visual_semantic data.

Usage:
    python scripts/ingest_v2.py
"""

import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from tqdm import tqdm

from core.embeddings import embed, embed_batch
from config.settings import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTIONS


# Knowledge base data
MATERIAL_KNOWLEDGE = [
    {
        "topic": "material",
        "material": "merino_wool",
        "category": "fabric",
        "content": "Merino wool is soft, temperature-regulating, and moisture-wicking. Warm in cold but breathable in mild weather. Fine fiber means less itch than regular wool.",
        "properties": "Soft, breathable, moisture-wicking, odor-resistant",
        "skin_notes": "Generally hypoallergenic. Safe for most sensitive skin and mild eczema. Rare allergy to lanolin possible.",
        "warmth_range": "Mild to cold (-5 to 15C with layering)",
        "care_instructions": "Hand wash or gentle machine wash. Lay flat to dry."
    },
    {
        "topic": "material",
        "material": "duck_down",
        "category": "insulation",
        "content": "Duck down provides excellent warmth-to-weight ratio. Very compressible. Loses insulation when wet.",
        "properties": "Lightweight, compressible, excellent insulation",
        "skin_notes": "Outer shell is typically polyester/nylon - no direct skin contact. Rare feather allergy possible.",
        "warmth_range": "Cold to extreme cold. 400g fill: -5C. 600g fill: -15C. 800g+: -20C and below",
        "care_instructions": "Professional cleaning recommended. Can be machine washed with special detergent."
    },
    {
        "topic": "material",
        "material": "cotton",
        "category": "fabric",
        "content": "Cotton is soft and breathable. Absorbs moisture but dries slowly. Not warm when wet.",
        "properties": "Soft, breathable, comfortable, affordable",
        "skin_notes": "Most skin-friendly fabric. Excellent for sensitive skin and allergies.",
        "warmth_range": "Spring/autumn, room temperature. Not suitable for cold outdoor wear.",
        "care_instructions": "Machine washable. Tumble dry or air dry."
    },
    {
        "topic": "material",
        "material": "polyester",
        "category": "fabric",
        "content": "Polyester is durable, quick-drying, and affordable. Less breathable than natural fibers. Retains shape well.",
        "properties": "Durable, quick-dry, wrinkle-resistant, affordable",
        "skin_notes": "May cause irritation for very sensitive skin. Can trap heat and sweat.",
        "warmth_range": "Depends on weave. Fleece polyester: mild to cold.",
        "care_instructions": "Machine washable. Quick to dry."
    },
    {
        "topic": "material",
        "material": "cashmere",
        "category": "fabric",
        "content": "Cashmere is ultra-soft and luxurious. Provides excellent warmth for weight. Requires careful care.",
        "properties": "Ultra-soft, lightweight, warm, luxurious",
        "skin_notes": "Usually well-tolerated by sensitive skin. Very fine fibers reduce itch.",
        "warmth_range": "Cold weather (0 to 10C)",
        "care_instructions": "Dry clean or very gentle hand wash. Lay flat to dry."
    }
]


def get_client():
    """Get Qdrant client."""
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def ingest_products(products_data, client=None):
    """Ingest products into products_v2 collection."""
    if client is None:
        client = get_client()
    
    collection_name = QDRANT_COLLECTIONS["products"]
    
    print(f"\n[Products] Preparing {len(products_data)} products...")
    
    # Prepare texts for batch embedding
    texts = [f"{p['name']}: {p['description']}" for p in products_data]
    
    print(f"[Products] Generating embeddings...")
    vectors = embed_batch(texts, show_progress=True)
    
    points = []
    for i, product in enumerate(products_data):
        points.append(PointStruct(
            id=i,
            vector=vectors[i],
            payload={
                "asin": product["id"],
                "name": product["name"],
                "brand": product["brand"],
                "category": product["category"],
                "price": product["price"],
                "description": product["description"],
                "rating": product.get("rating", 4.0),
                "review_count": len(product.get("reviews", [])),
                "image_url": product.get("image_url", ""),
                "attributes": {
                    "color": product.get("color", ""),
                    "material": product.get("material", ""),
                }
            }
        ))
    
    print(f"[Products] Upserting to Qdrant...")
    client.upsert(collection_name=collection_name, points=points)
    print(f"✓ Ingested {len(points)} products")
    
    return len(points)


def ingest_reviews(products_data, client=None):
    """Ingest reviews into reviews_v2 collection."""
    if client is None:
        client = get_client()
    
    collection_name = QDRANT_COLLECTIONS["reviews"]
    
    # Collect all reviews
    all_reviews = []
    for product in products_data:
        for review in product.get("reviews", []):
            all_reviews.append({
                "asin": product["id"],
                "text": review["text"],
                "rating": review["rating"],
                "reviewer_height": review.get("reviewer_height"),
                "reviewer_weight": review.get("reviewer_weight"),
                "sentiment": "positive" if review["rating"] >= 4 else "negative" if review["rating"] <= 2 else "neutral",
                "verified_purchase": True
            })
    
    print(f"\n[Reviews] Preparing {len(all_reviews)} reviews...")
    
    # Prepare texts for batch embedding
    texts = [r["text"] for r in all_reviews]
    
    print(f"[Reviews] Generating embeddings...")
    vectors = embed_batch(texts, show_progress=True)
    
    points = []
    for i, review in enumerate(all_reviews):
        points.append(PointStruct(
            id=i,
            vector=vectors[i],
            payload=review
        ))
    
    print(f"[Reviews] Upserting to Qdrant...")
    client.upsert(collection_name=collection_name, points=points)
    print(f"✓ Ingested {len(points)} reviews")
    
    return len(points)


def ingest_knowledge(client=None):
    """Ingest knowledge into knowledge_v2 collection."""
    if client is None:
        client = get_client()
    
    collection_name = QDRANT_COLLECTIONS["knowledge"]
    
    print(f"\n[Knowledge] Preparing {len(MATERIAL_KNOWLEDGE)} knowledge items...")
    
    # Prepare texts for batch embedding
    texts = []
    for item in MATERIAL_KNOWLEDGE:
        text = f"{item['material']}: {item['content']} {item['properties']} Skin notes: {item['skin_notes']} Warmth: {item['warmth_range']}"
        texts.append(text)
    
    print(f"[Knowledge] Generating embeddings...")
    vectors = embed_batch(texts, show_progress=True)
    
    points = []
    for i, item in enumerate(MATERIAL_KNOWLEDGE):
        points.append(PointStruct(
            id=i,
            vector=vectors[i],
            payload=item
        ))
    
    print(f"[Knowledge] Upserting to Qdrant...")
    client.upsert(collection_name=collection_name, points=points)
    print(f"✓ Ingested {len(points)} knowledge items")
    
    return len(points)


def ingest_visual_semantic(products_data, client=None):
    """Ingest visual descriptions into visual_semantic_v2 collection.
    
    For demo purposes, we generate simple visual descriptions from product data.
    In production, this would use a VLM to analyze actual product images.
    """
    if client is None:
        client = get_client()
    
    collection_name = QDRANT_COLLECTIONS["visual_semantic"]
    
    print(f"\n[Visual] Preparing visual descriptions...")
    
    visual_items = []
    for product in products_data:
        # Generate visual description from product description
        desc = product["description"]
        
        # Extract color (simple heuristic)
        color = ""
        color_keywords = ["navy", "black", "white", "grey", "gray", "blue", "red", "green", "brown", "beige", "camel", "pink"]
        for keyword in color_keywords:
            if keyword in desc.lower():
                color = keyword
                break
        
        # Generate visual description
        visual_desc = f"Product: {product['name']}. Description: {desc[:200]}"
        
        visual_items.append({
            "asin": product["id"],
            "image_type": "main",
            "description": visual_desc,
            "attributes": {
                "color": color,
                "style": product.get("category", ""),
            }
        })
    
    # Prepare texts for batch embedding
    texts = [v["description"] for v in visual_items]
    
    print(f"[Visual] Generating embeddings...")
    vectors = embed_batch(texts, show_progress=True)
    
    points = []
    for i, item in enumerate(visual_items):
        points.append(PointStruct(
            id=i,
            vector=vectors[i],
            payload=item
        ))
    
    print(f"[Visual] Upserting to Qdrant...")
    client.upsert(collection_name=collection_name, points=points)
    print(f"✓ Ingested {len(points)} visual descriptions")
    
    return len(points)


def main():
    """Main entry point."""
    print("=" * 60)
    print("ShopSense Data Ingestion v2")
    print("=" * 60)
    
    # Load product data
    print("\nLoading product data...")
    with open("data/sample_products.json") as f:
        products_data = json.load(f)
    print(f"Loaded {len(products_data)} products")
    
    # Get client
    client = get_client()
    
    # Check connection
    try:
        client.get_collections()
        print("✓ Connected to Qdrant\n")
    except Exception as e:
        print(f"✗ Failed to connect to Qdrant: {e}")
        sys.exit(1)
    
    # Ingest data
    stats = {}
    
    stats["products"] = ingest_products(products_data, client)
    stats["reviews"] = ingest_reviews(products_data, client)
    stats["knowledge"] = ingest_knowledge(client)
    stats["visual_semantic"] = ingest_visual_semantic(products_data, client)
    
    # Summary
    print("\n" + "=" * 60)
    print("Ingestion Complete!")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"  Products: {stats['products']}")
    print(f"  Reviews: {stats['reviews']}")
    print(f"  Knowledge: {stats['knowledge']}")
    print(f"  Visual Semantic: {stats['visual_semantic']}")
    print(f"\nTotal: {sum(stats.values())} items")


if __name__ == "__main__":
    main()
