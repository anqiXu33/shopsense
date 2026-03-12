"""agent/tools/visual.py

Visual semantic search tool using pre-computed visual descriptions.
"""

import time
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from agent.tools.base import BaseTool, ToolResult, ToolSchema, register_tool
from core.embeddings import embed
from config.settings import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTIONS


@register_tool
class VisualSemanticSearchTool(BaseTool):
    """Tool for searching pre-computed visual descriptions."""
    
    schema = ToolSchema(
        name="visual_semantic_search",
        description="基于预生成的视觉描述进行语义搜索。不需要实时调用 VLM，直接搜索已存储的视觉语义向量。当用户询问颜色、款式、版型等视觉属性时使用。",
        parameters={
            "asin": {
                "type": "string",
                "description": "商品 ASIN"
            },
            "query": {
                "type": "string",
                "description": "视觉查询，如'颜色'、'版型'、'细节'、'深蓝色'"
            },
            "top_k": {
                "type": "integer",
                "default": 3,
                "description": "返回结果数量"
            }
        },
        required=["asin", "query"]
    )
    
    def __init__(self):
        super().__init__()
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        self.collection_name = QDRANT_COLLECTIONS["visual_semantic"]
    
    async def execute(
        self,
        asin: str,
        query: str,
        top_k: int = 3
    ) -> ToolResult:
        """Execute visual semantic search."""
        start_time = time.time()
        
        try:
            # Generate embedding
            vector = embed(query)
            
            # Build filter for ASIN
            query_filter = Filter(
                must=[FieldCondition(key="asin", match=MatchValue(value=asin))]
            )
            
            # Query Qdrant
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=vector,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
                with_vectors=False
            )
            
            # Format results
            visual_items = []
            for point in results.points:
                item = {
                    "asin": point.payload.get("asin"),
                    "image_type": point.payload.get("image_type"),
                    "description": point.payload.get("description"),
                    "attributes": point.payload.get("attributes", {}),
                    "relevance_score": round(point.score, 4)
                }
                visual_items.append(item)
            
            execution_time = (time.time() - start_time) * 1000
            
            avg_relevance = sum(v["relevance_score"] for v in visual_items) / len(visual_items) if visual_items else 0
            
            return ToolResult(
                tool_name=self.schema.name,
                success=True,
                data={
                    "visual_items": visual_items,
                    "total_found": len(visual_items),
                    "query": query,
                    "asin": asin
                },
                relevance_score=avg_relevance,
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
