"""scripts/ingest_all.py

Ingest all static data into Qdrant collections.
Reads from data/ directory, embeds with sentence-transformers, uploads to Qdrant Cloud.

Usage:
    python scripts/ingest_all.py
"""

import json
import sys
import os
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, FilterSelector, Filter
from config.settings import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTIONS
from core.embeddings import embed_batch

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)

PRODUCTS = [
    {
        "asin": "P001",
        "name": "Alpine Duck Down Jacket",
        "brand": "NorthPeak",
        "category": "outerwear",
        "price": 129.99,
        "rating": 3.7,
        "review_count": 6,
        "image_url": "https://media.maisonkitsune.com/media/catalog/product/cache/5b6799a1e14ed1d66eedf309ab07601e/p/m/pm02221wq4064-0413_1_1.jpg",
        "description": "Duck down fill 450g, deep navy blue color, wind-resistant matte shell, removable hood with adjustable drawstring, two zip side pockets and one inner chest pocket, ribbed cuffs, slightly fitted silhouette, logo patch on left chest.",
        "attributes": {"color": "navy blue", "material": "duck down + polyester shell"},
    },
    {
        "asin": "P002",
        "name": "Waterproof Trench Coat",
        "brand": "UrbanShell",
        "category": "outerwear",
        "price": 189.99,
        "rating": 4.2,
        "review_count": 5,
        "image_url": "https://images.unsplash.com/photo-1539533018447-63fcce2678e3?auto=format&fit=crop&w=800&q=80",
        "description": "100% polyester with waterproof membrane, classic khaki beige, double-breasted button front, belted waist, storm flap at shoulders, knee length, removable wool-blend inner lining, structured collar.",
        "attributes": {
            "color": "khaki beige",
            "material": "polyester + waterproof membrane",
        },
    },
    {
        "asin": "P003",
        "name": "Merino Wool Turtleneck",
        "brand": "WoolCraft",
        "category": "knitwear",
        "price": 89.99,
        "rating": 4.6,
        "review_count": 8,
        "image_url": "https://ecdn.speedsize.com/90526ea8-ead7-46cf-ba09-f3be94be750a/www.boggi.com/dw/image/v2/BBBS_PRD/on/demandware.static/-/Sites-BoggiCatalog/default/dw0741ab18/images/hi-res/BO25A076004_1.jpeg",
        "description": "100% extra-fine merino wool, classic ivory white, ribbed turtleneck collar, relaxed fit, temperature-regulating and naturally odor-resistant. Safe for sensitive skin.",
        "attributes": {"color": "ivory white", "material": "100% merino wool"},
    },
    {
        "asin": "P004",
        "name": "Cashmere Blend Scarf",
        "brand": "LuxeKnit",
        "category": "accessories",
        "price": 59.99,
        "rating": 4.8,
        "review_count": 12,
        "image_url": "https://images.unsplash.com/photo-1520903920243-00d872a2d1c9?auto=format&fit=crop&w=800&q=80",
        "description": "70% cashmere 30% silk, warm camel brown, 180cm length, fringe edges, ultra-lightweight and exceptionally warm for its weight.",
        "attributes": {"color": "camel brown", "material": "cashmere + silk blend"},
    },
    {
        "asin": "P005",
        "name": "Fleece Zip-Up Hoodie",
        "brand": "CozyLayer",
        "category": "casual",
        "price": 49.99,
        "rating": 4.3,
        "review_count": 15,
        "image_url": "https://cdn-images.farfetch-contents.com/32/30/23/76/32302376_62445519_2048.jpg",
        "description": "100% recycled polyester fleece, heather grey, full-zip front, kangaroo pocket, adjustable hood, relaxed fit. Brushed interior for extra softness.",
        "attributes": {
            "color": "heather grey",
            "material": "recycled polyester fleece",
        },
    },
    {
        "asin": "P006",
        "name": "Cotton Oxford Shirt",
        "brand": "ClassicFit",
        "category": "shirts",
        "price": 45.99,
        "rating": 4.1,
        "review_count": 20,
        "image_url": "https://ecdn.speedsize.com/90526ea8-ead7-46cf-ba09-f3be94be750a/www.boggi.com/dw/image/v2/BBBS_PRD/on/demandware.static/-/Sites-BoggiCatalog/default/dw330844f2/images/hi-res/BO25A056901_5.jpeg",
        "description": "100% cotton oxford weave, crisp white, button-down collar, chest pocket, slim fit, machine washable. Breathable and comfortable for all-day wear.",
        "attributes": {"color": "white", "material": "100% cotton"},
    },
    {
        "asin": "P007",
        "name": "Thermal Base Layer Set",
        "brand": "ThermoCore",
        "category": "activewear",
        "price": 69.99,
        "rating": 4.5,
        "review_count": 9,
        "image_url": "https://media.revolutionrace.com/api/media/image/b6f878b2-d01e-4ce2-83e0-cc840f0edd04/image.jpg?width=1200",
        "description": "Merino wool blend, charcoal grey, moisture-wicking, quick-dry, flatlock seams to prevent chafing. Top and bottom set, ideal for winter sports and cold commutes.",
        "attributes": {"color": "charcoal grey", "material": "merino wool blend"},
    },
    {
        "asin": "P008",
        "name": "Windproof Softshell Jacket",
        "brand": "TrailBlaze",
        "category": "outerwear",
        "price": 159.99,
        "rating": 4.4,
        "review_count": 7,
        "image_url": "https://media.revolutionrace.com/api/media/image/db6235c8-5134-4fad-9993-934927801591/image.jpg?width=1200",
        "description": "3-layer softshell fabric, forest green, windproof and water-resistant, articulated stretch panels for freedom of movement, zippered chest and hand pockets.",
        "attributes": {"color": "forest green", "material": "softshell polyester"},
    },
    {
        "asin": "P009",
        "name": "Linen Summer Shirt",
        "brand": "BreezeWear",
        "category": "shirts",
        "price": 55.99,
        "rating": 4.2,
        "review_count": 11,
        "image_url": "https://frame-store.com/cdn/shop/files/MS26WSH003_BLST-MS26WPA003_DKNV_00942.jpg?v=1767730004&width=1280",
        "description": "100% Belgian linen, sky blue, relaxed fit, chest pocket, single button cuffs. Naturally breathable and lightweight, ideal for warm weather and humid climates.",
        "attributes": {"color": "sky blue", "material": "100% Belgian linen"},
    },
    {
        "asin": "P010",
        "name": "Quilted Puffer Vest",
        "brand": "AlpineStyle",
        "category": "outerwear",
        "price": 89.99,
        "rating": 4.0,
        "review_count": 6,
        "image_url": "https://aurelien-online.com/cdn/shop/files/aurelien_body_warmer_jacket_cashmere_blend_navy1_a51648b4-10e0-45fe-98aa-2bc09d86260f.jpg?v=1759496270&width=1400",
        "description": "Synthetic fill, matte black, quilted diamond stitching, full-zip front, interior security pocket, slim fit, packable into its own pocket.",
        "attributes": {
            "color": "dark blue",
            "material": "synthetic fill + nylon shell",
        },
    },
    {
        "asin": "P011",
        "name": "Stretch Denim Jeans",
        "brand": "DenimLab",
        "category": "bottoms",
        "price": 95.99,
        "rating": 4.3,
        "review_count": 18,
        "image_url": "https://images.unsplash.com/photo-1542272604-787c3835535d?auto=format&fit=crop&w=800&q=80",
        "description": "98% cotton 2% elastane, indigo blue, slim straight cut, five-pocket design, reinforced belt loops, slightly tapered at the ankle.",
        "attributes": {"color": "indigo blue", "material": "cotton + elastane"},
    },
    {
        "asin": "P012",
        "name": "Lounge Set",
        "brand": "EcoComfort",
        "category": "loungewear",
        "price": 75.99,
        "rating": 4.7,
        "review_count": 14,
        "image_url": "https://image01.bonprix.ch/assets/880x1232/2x/1763992631/25163184-iScxMZl2.webp",
        "description": "95% bamboo viscose 5% spandex, sage green, ultra-soft to touch, naturally antibacterial and temperature-regulating. Relaxed top and tapered pants set.",
        "attributes": {"color": "sage green", "material": "bamboo viscose"},
    },
    {
        "asin": "P013",
        "name": "Merino Running Socks",
        "brand": "SockTech",
        "category": "accessories",
        "price": 29.99,
        "rating": 4.6,
        "review_count": 22,
        "image_url": "https://images.unsplash.com/photo-1586350977771-b3b0abd50c82?auto=format&fit=crop&w=800&q=80",
        "description": "60% merino wool, crew length, cushioned sole, arch support band, moisture-wicking and odor-resistant. 3-pack. Suitable for running, hiking, and everyday wear.",
        "attributes": {"color": "white/grey mix", "material": "merino wool blend"},
    },
    {
        "asin": "P014",
        "name": "Corduroy Overshirt",
        "brand": "LayerUp",
        "category": "shirts",
        "price": 79.99,
        "rating": 4.2,
        "review_count": 8,
        "image_url": "https://www.bfgcdn.com/1500_1500_90/033-2664-0311/passenger-backcountry-cord-shirt-hemd.jpg",
        "description": "100% cotton corduroy, rust orange, oversized shirt-jacket silhouette, two chest pockets with button flaps, button front, versatile as both a shirt and light outer layer.",
        "attributes": {"color": "rust orange", "material": "100% cotton corduroy"},
    },
    {
        "asin": "P015",
        "name": "Long Down Blanket Coat",
        "brand": "CoatCo",
        "category": "outerwear",
        "price": 219.99,
        "rating": 4.5,
        "review_count": 10,
        "image_url": "https://ch.oneill.com/cdn/shop/files/1500136_17525_01_MODEL.jpg?v=1749222969&width=2000",
        "description": "800-fill goose down, oyster white, ankle-length cocoon silhouette, concealed zip and button placket, stand collar, side slit pockets. Extremely warm for extreme cold.",
        "attributes": {
            "color": "oyster white",
            "material": "goose down + ripstop nylon",
        },
    },
]


def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ingest_products(client: QdrantClient):
    print("\n[Products] Ingesting 15 products...")
    collection = QDRANT_COLLECTIONS["products"]
    client.delete(collection_name=collection, points_selector=FilterSelector(filter=Filter()))

    texts = [
        f"{p['name']} {p['brand']} {p['category']} {p['description']}" for p in PRODUCTS
    ]
    vectors = embed_batch(texts, show_progress=True)

    points = []
    for i, product in enumerate(PRODUCTS):
        point_id = uuid.uuid5(uuid.NAMESPACE_DNS, product["asin"]).int >> 64
        points.append(
            PointStruct(
                id=point_id,
                vector=vectors[i],
                payload={
                    "asin": product["asin"],
                    "name": product["name"],
                    "brand": product["brand"],
                    "category": product["category"],
                    "price": product["price"],
                    "rating": product["rating"],
                    "review_count": product["review_count"],
                    "image_url": product["image_url"],
                    "description": product["description"],
                    "attributes": product["attributes"],
                },
            )
        )

    client.upsert(collection_name=collection, points=points)
    print(f"[Products] Uploaded {len(points)} products.")


def ingest_reviews(client: QdrantClient):
    reviews = load_json("reviews.json")
    print(f"\n[Reviews] Ingesting {len(reviews)} reviews...")
    collection = QDRANT_COLLECTIONS["reviews"]
    client.delete(collection_name=collection, points_selector=FilterSelector(filter=Filter()))

    texts = [r["text"] for r in reviews]
    vectors = embed_batch(texts, show_progress=True)

    points = []
    for i, review in enumerate(reviews):
        point_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{review['asin']}_{i}").int >> 64
        points.append(
            PointStruct(
                id=point_id,
                vector=vectors[i],
                payload={
                    "asin": review["asin"],
                    "text": review["text"],
                    "rating": review["rating"],
                    "reviewer_height": review.get("reviewer_height"),
                    "reviewer_weight": review.get("reviewer_weight"),
                    "sentiment": review.get("sentiment", "neutral"),
                    "verified_purchase": review.get("verified_purchase", True),
                },
            )
        )

    client.upsert(collection_name=collection, points=points)
    print(f"[Reviews] Uploaded {len(points)} reviews.")


def ingest_knowledge(client: QdrantClient):
    knowledge = load_json("knowledge.json")
    print(f"\n[Knowledge] Ingesting {len(knowledge)} entries...")
    collection = QDRANT_COLLECTIONS["knowledge"]
    client.delete(collection_name=collection, points_selector=FilterSelector(filter=Filter()))

    texts = [k["text"] for k in knowledge]
    vectors = embed_batch(texts, show_progress=True)

    points = []
    for i, entry in enumerate(knowledge):
        point_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{entry['topic']}_{i}").int >> 64
        points.append(
            PointStruct(
                id=point_id,
                vector=vectors[i],
                payload={
                    "topic": entry["topic"],
                    "material": entry["material"],
                    "category": entry["category"],
                    "text": entry["text"],
                },
            )
        )

    client.upsert(collection_name=collection, points=points)
    print(f"[Knowledge] Uploaded {len(points)} entries.")


def ingest_visual_semantic(client: QdrantClient):
    visual = load_json("visual_semantic.json")
    print(f"\n[Visual] Ingesting {len(visual)} image descriptions...")
    collection = QDRANT_COLLECTIONS["visual_semantic"]
    client.delete(collection_name=collection, points_selector=FilterSelector(filter=Filter()))

    texts = [v["text"] for v in visual]
    vectors = embed_batch(texts, show_progress=True)

    points = []
    for i, entry in enumerate(visual):
        point_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{entry['asin']}_visual_{i}").int >> 64
        points.append(
            PointStruct(
                id=point_id,
                vector=vectors[i],
                payload={
                    "asin": entry["asin"],
                    "image_type": entry["image_type"],
                    "text": entry["text"],
                },
            )
        )

    client.upsert(collection_name=collection, points=points)
    print(f"[Visual] Uploaded {len(points)} entries.")


def main():
    print("=" * 60)
    print("ShopSense Data Ingestion")
    print("=" * 60)

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    try:
        client.get_collections()
        print("✓ Connected to Qdrant")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        sys.exit(1)

    ingest_products(client)
    ingest_reviews(client)
    ingest_knowledge(client)
    ingest_visual_semantic(client)

    print("\n" + "=" * 60)
    print("Ingestion complete!")
    print("=" * 60)

    for name in QDRANT_COLLECTIONS.values():
        info = client.get_collection(name)
        print(f"  {name}: {info.points_count} points")


if __name__ == "__main__":
    main()
