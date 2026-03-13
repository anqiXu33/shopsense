"""agent/tools/recommend.py

Recommendation tool based on positive/negative examples.
"""

import time
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient

from agent.tools.base import BaseTool, ToolResult, ToolSchema, register_tool
from config.settings import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTIONS


@register_tool
class RecommendByExampleTool(BaseTool):
    """Tool for recommending products based on positive/negative examples."""
    
    schema = ToolSchema(
        name="recommend_by_example",
        description="使用 Qdrant Recommend API 基于正/负例推荐商品。当用户表达偏好（'我喜欢A和B，不喜欢C'）时，推荐相似商品。",
        parameters={
            "positive_asins": {
                "type": "array",
                "items": {"type": "string"},
                "description": "喜欢的商品 ASIN 列表"
            },
            "negative_asins": {
                "type": "array",
                "items": {"type": "string"},
                "description": "不喜欢的商品 ASIN 列表"
            },
            "limit": {
                "type": "integer",
                "default": 5,
                "description": "推荐数量"
            }
        },
        required=["positive_asins"]
    )
    
    def __init__(self):
        super().__init__()
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        self.collection_name = QDRANT_COLLECTIONS["products"]
    
    async def execute(
        self,
        positive_asins: List[str],
        negative_asins: Optional[List[str]] = None,
        limit: int = 5
    ) -> ToolResult:
        """Execute recommendation by example using vector similarity."""
        start_time = time.time()
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            def get_point_id(asin: str) -> Optional[int]:
                results = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=Filter(
                        must=[FieldCondition(key="asin", match=MatchValue(value=asin))]
                    ),
                    limit=1
                )[0]
                return results[0].id if results else None
            
            # Get positive example vectors and calculate average
            positive_vectors = []
            for asin in positive_asins:
                pid = get_point_id(asin)
                if pid is not None:
                    point = self.client.retrieve(
                        collection_name=self.collection_name,
                        ids=[pid],
                        with_vectors=True
                    )[0]
                    if hasattr(point.vector, 'get'):
                        # Handle dict-like vector
                        vec = list(point.vector.values())[0] if point.vector else None
                    else:
                        vec = point.vector
                    if vec:
                        positive_vectors.append(vec)
            
            if not positive_vectors:
                return ToolResult(
                    tool_name=self.schema.name,
                    success=False,
                    data=None,
                    error_message="No valid positive examples found",
                    relevance_score=0.0
                )
            
            # Calculate average vector
            import numpy as np
            avg_vector = np.mean(positive_vectors, axis=0).tolist()
            
            # Get negative example IDs to exclude
            exclude_ids = set()
            if negative_asins:
                for asin in negative_asins:
                    pid = get_point_id(asin)
                    if pid is not None:
                        exclude_ids.add(pid)
            
            # Also exclude positive examples
            for asin in positive_asins:
                pid = get_point_id(asin)
                if pid is not None:
                    exclude_ids.add(pid)
            
            # Search for similar products
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=avg_vector,
                limit=limit + len(exclude_ids),
                with_payload=True
            )
            
            # Format results (excluding positive/negative examples)
            products = []
            for point in results.points:
                if point.id in exclude_ids:
                    continue
                product = {
                    "asin": point.payload.get("asin"),
                    "name": point.payload.get("name"),
                    "brand": point.payload.get("brand"),
                    "category": point.payload.get("category"),
                    "price": point.payload.get("price"),
                    "rating": point.payload.get("rating"),
                    "review_count": point.payload.get("review_count"),
                    "description": point.payload.get("description", "")[:150],
                    "image_url": point.payload.get("image_url"),
                    "recommendation_score": round(point.score, 4)
                }
                products.append(product)
                if len(products) >= limit:
                    break
            
            execution_time = (time.time() - start_time) * 1000
            
            avg_score = sum(p["recommendation_score"] for p in products) / len(products) if products else 0
            
            return ToolResult(
                tool_name=self.schema.name,
                success=True,
                data={
                    "recommendations": products,
                    "total_found": len(products),
                    "positive_examples": positive_asins,
                    "negative_examples": negative_asins or []
                },
                relevance_score=avg_score,
                execution_time_ms=execution_time,
                metadata={
                    "collection": self.collection_name
                }
            )
            
        except Exception as e:
            return ToolResult(
                tool_name=self.schema.name,
                success=False,
                data=None,
                error_message=str(e),
                relevance_score=0.0
            )
