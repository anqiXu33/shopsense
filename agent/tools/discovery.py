"""agent/tools/discovery.py

Discovery tool for finding similar/dissimilar products using Qdrant Discovery API.
"""

import time
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient

from agent.tools.base import BaseTool, ToolResult, ToolSchema, register_tool
from config.settings import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTIONS


@register_tool
class DiscoverySimilarTool(BaseTool):
    """Tool for discovering similar products using Qdrant Discovery API."""
    
    schema = ToolSchema(
        name="discovery_similar",
        description="使用 Qdrant Discovery API 找与目标相似或相反的商品。支持'像A但不像B'的复杂查询。当用户想要类似商品、或需要对比不同选项时使用。",
        parameters={
            "target_asin": {
                "type": "string",
                "description": "目标商品 ASIN"
            },
            "positive_examples": {
                "type": "array",
                "items": {"type": "string"},
                "description": "正面示例 ASIN 列表（希望相似的）"
            },
            "negative_examples": {
                "type": "array",
                "items": {"type": "string"},
                "description": "负面示例 ASIN 列表（希望不同的）"
            },
            "context": {
                "type": "string",
                "description": "对比维度，如'保暖性'、'价格'、'版型'"
            },
            "top_k": {
                "type": "integer",
                "default": 5,
                "description": "返回结果数量"
            }
        },
        required=["target_asin"]
    )
    
    def __init__(self):
        super().__init__()
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        self.collection_name = QDRANT_COLLECTIONS["products"]
    
    async def execute(
        self,
        target_asin: str,
        positive_examples: Optional[List[str]] = None,
        negative_examples: Optional[List[str]] = None,
        context: Optional[str] = None,
        top_k: int = 5
    ) -> ToolResult:
        """Execute discovery search."""
        start_time = time.time()
        
        try:
            # Helper function to convert ASIN to point ID
            def get_point_id(asin: str) -> Optional[int]:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                results = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=Filter(
                        must=[FieldCondition(key="asin", match=MatchValue(value=asin))]
                    ),
                    limit=1
                )[0]
                return results[0].id if results else None
            
            # Get target point ID
            target_id = get_point_id(target_asin)
            if target_id is None:
                return ToolResult(
                    tool_name=self.schema.name,
                    success=False,
                    data=None,
                    error_message=f"Target product {target_asin} not found",
                    relevance_score=0.0
                )
            
            # Convert positive/negative ASINs to IDs
            positive_ids = [target_id]
            if positive_examples:
                for asin in positive_examples:
                    pid = get_point_id(asin)
                    if pid is not None:
                        positive_ids.append(pid)
            
            negative_ids = []
            if negative_examples:
                for asin in negative_examples:
                    pid = get_point_id(asin)
                    if pid is not None:
                        negative_ids.append(pid)
            
            # Get target vector and search for similar products
            target_point = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[target_id],
                with_vectors=True
            )[0]
            
            # Search for similar products using vector similarity
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=target_point.vector,
                limit=top_k + 1,  # +1 to exclude target itself
                with_payload=True
            )
            
            # Format results (exclude target product)
            products = []
            for point in results.points:
                # Skip the target product itself
                if point.payload.get("asin") == target_asin:
                    continue
                product = {
                    "asin": point.payload.get("asin"),
                    "name": point.payload.get("name"),
                    "brand": point.payload.get("brand"),
                    "price": point.payload.get("price"),
                    "rating": point.payload.get("rating"),
                    "similarity_score": round(point.score, 4)
                }
                products.append(product)
            
            # Limit to top_k
            products = products[:top_k]
            
            execution_time = (time.time() - start_time) * 1000
            
            avg_score = sum(p["similarity_score"] for p in products) / len(products) if products else 0
            
            return ToolResult(
                tool_name=self.schema.name,
                success=True,
                data={
                    "target_asin": target_asin,
                    "similar_products": products,
                    "total_found": len(products),
                    "context": context
                },
                relevance_score=avg_score,
                execution_time_ms=execution_time,
                metadata={
                    "used_recommend_api": True,
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
