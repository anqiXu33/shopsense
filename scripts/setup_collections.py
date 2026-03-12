"""scripts/setup_collections.py

创建 Qdrant collections 和索引。
根据设计文档，创建 4 个核心 collections：
- products: 商品语义搜索
- reviews: 评价语义搜索
- knowledge: 专业知识
- visual_semantic: 视觉语义

Usage:
    python scripts/setup_collections.py
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PayloadSchemaType,
)
from config.settings import QDRANT_URL, QDRANT_API_KEY, VECTOR_SIZE, QDRANT_COLLECTIONS


def get_client():
    """Get Qdrant client instance."""
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def setup_products_collection(client: QdrantClient):
    """Setup products collection with indexes."""
    collection_name = QDRANT_COLLECTIONS["products"]
    
    # Check if exists
    collections = client.get_collections().collections
    existing = [c.name for c in collections]
    
    if collection_name in existing:
        print(f"Collection '{collection_name}' already exists, skipping creation.")
    else:
        # Create collection with cosine distance
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE
            )
        )
        print(f"✓ Created collection: {collection_name}")
    
    # Create payload indexes for filtering
    indexes = [
        ("asin", PayloadSchemaType.KEYWORD),
        ("brand", PayloadSchemaType.KEYWORD),
        ("category", PayloadSchemaType.KEYWORD),
        ("price", PayloadSchemaType.FLOAT),
        ("rating", PayloadSchemaType.FLOAT),
    ]
    
    for field_name, field_type in indexes:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_type
            )
            print(f"  ✓ Created index: {field_name}")
        except Exception as e:
            print(f"  ⚠ Index {field_name} may already exist: {e}")


def setup_reviews_collection(client: QdrantClient):
    """Setup reviews collection with indexes."""
    collection_name = QDRANT_COLLECTIONS["reviews"]
    
    collections = client.get_collections().collections
    existing = [c.name for c in collections]
    
    if collection_name in existing:
        print(f"Collection '{collection_name}' already exists, skipping creation.")
    else:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE
            )
        )
        print(f"✓ Created collection: {collection_name}")
    
    indexes = [
        ("asin", PayloadSchemaType.KEYWORD),
        ("rating", PayloadSchemaType.INTEGER),
        ("sentiment", PayloadSchemaType.KEYWORD),
        ("reviewer_height", PayloadSchemaType.INTEGER),
        ("reviewer_weight", PayloadSchemaType.INTEGER),
        ("verified_purchase", PayloadSchemaType.BOOL),
    ]
    
    for field_name, field_type in indexes:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_type
            )
            print(f"  ✓ Created index: {field_name}")
        except Exception as e:
            print(f"  ⚠ Index {field_name} may already exist: {e}")


def setup_knowledge_collection(client: QdrantClient):
    """Setup knowledge collection with indexes."""
    collection_name = QDRANT_COLLECTIONS["knowledge"]
    
    collections = client.get_collections().collections
    existing = [c.name for c in collections]
    
    if collection_name in existing:
        print(f"Collection '{collection_name}' already exists, skipping creation.")
    else:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE
            )
        )
        print(f"✓ Created collection: {collection_name}")
    
    indexes = [
        ("topic", PayloadSchemaType.KEYWORD),
        ("material", PayloadSchemaType.KEYWORD),
        ("category", PayloadSchemaType.KEYWORD),
    ]
    
    for field_name, field_type in indexes:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_type
            )
            print(f"  ✓ Created index: {field_name}")
        except Exception as e:
            print(f"  ⚠ Index {field_name} may already exist: {e}")


def setup_visual_semantic_collection(client: QdrantClient):
    """Setup visual_semantic collection with indexes."""
    collection_name = QDRANT_COLLECTIONS["visual_semantic"]
    
    collections = client.get_collections().collections
    existing = [c.name for c in collections]
    
    if collection_name in existing:
        print(f"Collection '{collection_name}' already exists, skipping creation.")
    else:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE
            )
        )
        print(f"✓ Created collection: {collection_name}")
    
    indexes = [
        ("asin", PayloadSchemaType.KEYWORD),
        ("image_type", PayloadSchemaType.KEYWORD),
    ]
    
    for field_name, field_type in indexes:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_type
            )
            print(f"  ✓ Created index: {field_name}")
        except Exception as e:
            print(f"  ⚠ Index {field_name} may already exist: {e}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("ShopSense Qdrant Collections Setup")
    print("=" * 60)
    print(f"\nQdrant URL: {QDRANT_URL}")
    print(f"Vector Size: {VECTOR_SIZE}")
    print()
    
    client = get_client()
    
    # Check connection
    try:
        client.get_collections()
        print("✓ Connected to Qdrant\n")
    except Exception as e:
        print(f"✗ Failed to connect to Qdrant: {e}")
        sys.exit(1)
    
    # Setup collections
    print("Setting up collections...\n")
    
    setup_products_collection(client)
    print()
    
    setup_reviews_collection(client)
    print()
    
    setup_knowledge_collection(client)
    print()
    
    setup_visual_semantic_collection(client)
    print()
    
    print("=" * 60)
    print("Setup complete!")
    print("=" * 60)
    
    # List all collections
    collections = client.get_collections().collections
    print(f"\nTotal collections: {len(collections)}")
    for c in collections:
        print(f"  - {c.name}")


if __name__ == "__main__":
    main()
