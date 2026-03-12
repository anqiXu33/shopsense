"""agent/tools/product_search.py

Semantic product search tool.
"""

import time
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny, Range

from agent.tools.base import BaseTool, ToolResult, ToolSchema, register_tool
from core.embeddings import embed
from config.settings import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTIONS


@register_tool
class SemanticProductSearchTool(BaseTool):
    """Tool for semantic product search with attribute filtering."""
    
    schema = ToolSchema(
        name="semantic_product_search",
        description="基于语义搜索商品。使用 Qdrant 的向量搜索查找相关商品。支持按价格、品牌、品类、评分过滤。当用户想找某类商品、或需要推荐相似商品时使用。",
        parameters={
            "query": {
                "type": "string",
                "description": "搜索查询，如'保暖的羽绒服'、'适合敏感肌的毛衣'"
            },
            "filters": {
                "type": "object",
                "description": "可选过滤条件",
                "properties": {
                    "price_min": {"type": "number", "description": "最低价格"},
                    "price_max": {"type": "number", "description": "最高价格"},
                    "brands": {"type": "array", "items": {"type": "string"}, "description": "品牌列表"},
                    "category": {"type": "string", "description": "品类"},
                    "rating_min": {"type": "number", "description": "最低评分"}
                }
            },
            "top_k": {
                "type": "integer",
                "default": 5,
                "description": "返回商品数量"
            }
        },
        required=["query"]
    )
    
    def __init__(self):
        super().__init__()
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        self.collection_name = QDRANT_COLLECTIONS["products"]
    
    async def execute(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> ToolResult:
        """Execute semantic product search."""
        start_time = time.time()
        
        try:
            # Generate embedding
            vector = embed(query)
            
            # Build filter conditions
            must_conditions = []
            if filters:
                if filters.get("price_min") is not None or filters.get("price_max") is not None:
                    must_conditions.append(
                        FieldCondition(
                            key="price",
                            range=Range(
                                gte=filters.get("price_min"),
                                lte=filters.get("price_max")
                            )
                        )
                    )
                
                if filters.get("brands"):
                    must_conditions.append(
                        FieldCondition(
                            key="brand",
                            match=MatchAny(any=filters["brands"])
                        )
                    )
                
                if filters.get("category"):
                    must_conditions.append(
                        FieldCondition(key="category", match=MatchValue(value=filters["category"]))
                    )
                
                if filters.get("rating_min") is not None:
                    must_conditions.append(
                        FieldCondition(
                            key="rating",
                            range=Range(gte=filters["rating_min"])
                        )
                    )
            
            # Query Qdrant
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=vector,
                query_filter=Filter(must=must_conditions) if must_conditions else None,
                limit=top_k,
                with_payload=True,
                with_vectors=False
            )
            
            # Format results
            products = []
            for point in results.points:
                product = {
                    "asin": point.payload.get("asin"),
                    "name": point.payload.get("name"),
                    "brand": point.payload.get("brand"),
                    "category": point.payload.get("category"),
                    "price": point.payload.get("price"),
                    "rating": point.payload.get("rating"),
                    "review_count": point.payload.get("review_count"),
                    "description": point.payload.get("description", "")[:200],
                    "image_url": point.payload.get("image_url"),
                    "relevance_score": round(point.score, 4)
                }
                products.append(product)
            
            execution_time = (time.time() - start_time) * 1000
            
            # Calculate average relevance for scoring
            avg_relevance = sum(p["relevance_score"] for p in products) / len(products) if products else 0
            
            return ToolResult(
                tool_name=self.schema.name,
                success=True,
                data={
                    "products": products,
                    "total_found": len(products),
                    "query": query
                },
                relevance_score=avg_relevance,
                execution_time_ms=execution_time,
                metadata={
                    "filters_applied": filters is not None,
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
