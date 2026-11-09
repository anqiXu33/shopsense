"""scripts/ingest_all.py

Load the shoe subset (Amazon Reviews 2023, see scripts/build_dataset.py)
into Qdrant. Collections are dropped and rebuilt, so the script can be rerun
at any time.

Inputs:
    data/shoes/products.json    scripts/build_dataset.py
    data/shoes/reviews.json     scripts/build_dataset.py
    data/shoes/highlights.json  scripts/build_highlights.py
    data/shoes/visual.json      scripts/generate_visual_descriptions.py

Usage:
    python scripts/ingest_all.py
"""

import json
import os
import sys
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from config.settings import QDRANT_COLLECTIONS, ROOT_DIR, get_qdrant_client
from core.embeddings import embed_batch
from scripts.setup_collections import setup_products_collection, setup_reviews_collection

DATA_DIR = os.path.join(ROOT_DIR, "data")
BATCH = 256


def load_json(*parts):
    with open(os.path.join(DATA_DIR, *parts)) as f:
        return json.load(f)


def point_id(key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def recreate(client: QdrantClient, name: str, setup) -> None:
    if client.collection_exists(name):
        client.delete_collection(name)
    setup(client)


def upsert(client: QdrantClient, collection: str, points: list) -> None:
    for i in range(0, len(points), BATCH):
        client.upsert(collection_name=collection, points=points[i:i + BATCH])


def ingest_products(client: QdrantClient):
    products = load_json("shoes", "products.json")
    highlights = load_json("shoes", "highlights.json")
    visual = load_json("shoes", "visual.json")
    print(f"\n[Products] Ingesting {len(products)} products...")
    collection = QDRANT_COLLECTIONS["products"]
    recreate(client, collection, setup_products_collection)

    texts = [f"{p['name']}. {p['category']}. {' '.join(p['features'])}" for p in products]
    vectors = embed_batch(texts, show_progress=True)
    points = [
        PointStruct(id=point_id(p["asin"]), vector=v, payload={
            **p,
            "highlights": highlights[p["asin"]],
            "appearance": {lang: visual[p["asin"]][lang] for lang in ("zh", "en")},
        })
        for p, v in zip(products, vectors)
    ]
    upsert(client, collection, points)
    print(f"[Products] Uploaded {len(points)} products.")


def ingest_reviews(client: QdrantClient):
    reviews = load_json("shoes", "reviews.json")
    names = {p["asin"]: p["name"] for p in load_json("shoes", "products.json")}
    print(f"\n[Reviews] Ingesting {len(reviews)} reviews...")
    collection = QDRANT_COLLECTIONS["reviews"]
    recreate(client, collection, setup_reviews_collection)

    # The product name goes into each review's vector. A review saying "great
    # grip on wet floors" matches a kitchen-shoe need whether it is about a
    # clog or a house slipper; with the name in the vector, the kind of shoe
    # counts too. In a side-by-side check this moved "running shoes for wide
    # feet" from 2 to 5 running shoes in the top 5.
    vectors = embed_batch([f"{names[r['asin']]}. {r['title']}. {r['text']}" for r in reviews], show_progress=True)
    points = [
        PointStruct(id=point_id(r["review_id"]), vector=v, payload=r)
        for r, v in zip(reviews, vectors)
    ]
    upsert(client, collection, points)
    print(f"[Reviews] Uploaded {len(points)} reviews.")


def main():
    print("=" * 60)
    print("ShopSense Data Ingestion")
    print("=" * 60)

    client = get_qdrant_client()

    ingest_products(client)
    ingest_reviews(client)

    print("\n" + "=" * 60)
    print("Ingestion complete!")
    print("=" * 60)
    for name in QDRANT_COLLECTIONS.values():
        print(f"  {name}: {client.count(name).count} points")


if __name__ == "__main__":
    main()
