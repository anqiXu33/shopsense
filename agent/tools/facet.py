"""agent/tools/facet.py

Facet insights tool for statistical analysis of reviews.
"""

import time
from typing import Any, Dict, Optional
from collections import Counter

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from agent.tools.base import BaseTool, ToolResult, ToolSchema, register_tool
from core.embeddings import embed
from config.settings import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTIONS


@register_tool
class FacetInsightsTool(BaseTool):
    """Tool for faceted statistical analysis of reviews."""
    
    schema = ToolSchema(
        name="facet_insights",
        description="使用 Qdrant Facet API 对评价进行分面统计。快速了解各评分、尺码、情感的评价分布。当需要统计洞察、了解整体评价趋势时使用。",
        parameters={
            "asin": {
                "type": "string",
                "description": "商品 ASIN"
            },
            "facet_key": {
                "type": "string",
                "enum": ["rating", "sentiment"],
                "description": "分面维度"
            },
            "query": {
                "type": "string",
                "description": "可选过滤查询，如'尺码'只统计提到尺码的评价"
            },
            "limit": {
                "type": "integer",
                "default": 10,
                "description": "返回分面值数量"
            }
        },
        required=["asin", "facet_key"]
    )
    
    def __init__(self):
        super().__init__()
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        self.collection_name = QDRANT_COLLECTIONS["reviews"]
    
    async def execute(
        self,
        asin: str,
        facet_key: str,
        query: Optional[str] = None,
        limit: int = 10
    ) -> ToolResult:
        """Execute facet analysis."""
        start_time = time.time()
        
        try:
            # Build base filter for ASIN
            base_filter = Filter(
                must=[FieldCondition(key="asin", match=MatchValue(value=asin))]
            )
            
            if query:
                # Semantic filter: search relevant reviews first
                vector = embed(query)
                search_results = self.client.query_points(
                    collection_name=self.collection_name,
                    query=vector,
                    query_filter=base_filter,
                    limit=100,
                    with_payload=True
                )
                
                # Manual facet counting
                values = []
                for point in search_results.points:
                    val = point.payload.get(facet_key)
                    if val is not None:
                        values.append(val)
                
                counter = Counter(values)
                distribution = dict(counter.most_common(limit))
                
                total_reviews = len(values)
            else:
                # Use Facet API if available, otherwise fallback to counting
                try:
                    facet_result = self.client.facet(
                        collection_name=self.collection_name,
                        key=facet_key,
                        facet_filter=base_filter,
                        limit=limit
                    )
                    distribution = {item.key: item.count for item in facet_result}
                    total_reviews = sum(distribution.values())
                except Exception:
                    # Fallback: count manually
                    all_points = self.client.scroll(
                        collection_name=self.collection_name,
                        scroll_filter=base_filter,
                        limit=1000,
                        with_payload=True
                    )[0]
                    
                    values = [p.payload.get(facet_key) for p in all_points if p.payload.get(facet_key) is not None]
                    counter = Counter(values)
                    distribution = dict(counter.most_common(limit))
                    total_reviews = len(values)
            
            execution_time = (time.time() - start_time) * 1000
            
            return ToolResult(
                tool_name=self.schema.name,
                success=True,
                data={
                    "asin": asin,
                    "facet_key": facet_key,
                    "distribution": distribution,
                    "total_reviews": total_reviews,
                    "query": query
                },
                relevance_score=1.0,  # Statistical results are always relevant
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
