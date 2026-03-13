"""agent/tools/review_search.py

Semantic review search tool with multi-dimensional filtering.
"""

import time
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

from agent.tools.base import BaseTool, ToolResult, ToolSchema, register_tool
from core.embeddings import embed
from config.settings import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTIONS


@register_tool
class SemanticReviewSearchTool(BaseTool):
    """Tool for semantic review search with multi-dimensional filtering."""
    
    schema = ToolSchema(
        name="semantic_review_search",
        description="基于语义搜索用户评价。使用 Qdrant 向量搜索找相关反馈，支持按评分、身高、情感等过滤。可以只搜特定商品，也可以跨商品搜索。当用户询问具体使用体验、需要真实买家反馈时使用。",
        parameters={
            "query": {
                "type": "string",
                "description": "搜索主题，如'保暖性怎么样'、'尺码偏小'、'过敏反应'"
            },
            "asin": {
                "type": "string",
                "description": "指定商品 ASIN，可选。不指定则搜索所有商品"
            },
            "filters": {
                "type": "object",
                "description": "过滤条件",
                "properties": {
                    "sentiment": {
                        "type": "string",
                        "enum": ["positive", "negative", "neutral", "all"],
                        "description": "情感倾向"
                    },
                    "rating_min": {"type": "integer", "description": "最低评分 1-5"},
                    "rating_max": {"type": "integer", "description": "最高评分 1-5"},
                    "reviewer_height_min": {"type": "integer", "description": "评价者最小身高(cm)"},
                    "reviewer_height_max": {"type": "integer", "description": "评价者最大身高(cm)"},
                    "verified_only": {"type": "boolean", "description": "只看 verified purchase"}
                }
            },
            "top_k": {
                "type": "integer",
                "default": 5,
                "description": "返回评价数量"
            },
            "group_by_asin": {
                "type": "boolean",
                "default": False,
                "description": "是否按 ASIN 分组（对比场景）"
            }
        },
        required=["query"]
    )
    
    def __init__(self):
        super().__init__()
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        self.collection_name = QDRANT_COLLECTIONS["reviews"]
    
    async def execute(
        self,
        query: str,
        asin: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        group_by_asin: bool = False
    ) -> ToolResult:
        """Execute semantic review search."""
        start_time = time.time()
        
        try:
            # Generate embedding
            vector = embed(query)
            
            # Build filter conditions
            must_conditions = []
            
            if asin:
                must_conditions.append(
                    FieldCondition(key="asin", match=MatchValue(value=asin))
                )
            
            if filters:
                # Handle both 'sentiment' and 'sent' (LLM might truncate)
                sentiment = filters.get("sentiment") or filters.get("sent", "all")
                if sentiment != "all":
                    must_conditions.append(
                        FieldCondition(key="sentiment", match=MatchValue(value=sentiment))
                    )
                
                if filters.get("rating_min") is not None or filters.get("rating_max") is not None:
                    must_conditions.append(
                        FieldCondition(
                            key="rating",
                            range=Range(
                                gte=filters.get("rating_min"),
                                lte=filters.get("rating_max")
                            )
                        )
                    )
                
                if filters.get("reviewer_height_min") is not None or filters.get("reviewer_height_max") is not None:
                    must_conditions.append(
                        FieldCondition(
                            key="reviewer_height",
                            range=Range(
                                gte=filters.get("reviewer_height_min"),
                                lte=filters.get("reviewer_height_max")
                            )
                        )
                    )
                
                if filters.get("verified_only", True):
                    must_conditions.append(
                        FieldCondition(key="verified_purchase", match=MatchValue(value=True))
                    )
            
            # Query Qdrant
            if group_by_asin:
                # Use grouping API
                results = self.client.query_points_groups(
                    collection_name=self.collection_name,
                    query=vector,
                    query_filter=Filter(must=must_conditions) if must_conditions else None,
                    group_by="asin",
                    limit=top_k,
                    group_size=3,
                    with_payload=True
                )
                
                # Format grouped results
                groups = []
                for group in results.groups:
                    reviews = []
                    for point in group.hits:
                        review = {
                            "asin": point.payload.get("asin"),
                            "text": point.payload.get("text"),
                            "rating": point.payload.get("rating"),
                            "sentiment": point.payload.get("sentiment"),
                            "reviewer_height": point.payload.get("reviewer_height"),
                            "reviewer_weight": point.payload.get("reviewer_weight"),
                            "helpful_votes": point.payload.get("helpful_votes"),
                            "verified_purchase": point.payload.get("verified_purchase"),
                            "relevance_score": round(point.score, 4)
                        }
                        reviews.append(review)
                    
                    groups.append({
                        "asin": group.key,
                        "reviews": reviews,
                        "review_count": len(reviews)
                    })
                
                data = {
                    "groups": groups,
                    "total_groups": len(groups),
                    "query": query
                }
                
                # Calculate average relevance
                all_scores = []
                for g in groups:
                    for r in g["reviews"]:
                        all_scores.append(r["relevance_score"])
                avg_relevance = sum(all_scores) / len(all_scores) if all_scores else 0
                
            else:
                # Regular query
                results = self.client.query_points(
                    collection_name=self.collection_name,
                    query=vector,
                    query_filter=Filter(must=must_conditions) if must_conditions else None,
                    limit=top_k,
                    with_payload=True,
                    with_vectors=False
                )
                
                # Format results
                reviews = []
                for point in results.points:
                    review = {
                        "asin": point.payload.get("asin"),
                        "text": point.payload.get("text"),
                        "rating": point.payload.get("rating"),
                        "sentiment": point.payload.get("sentiment"),
                        "reviewer_height": point.payload.get("reviewer_height"),
                        "reviewer_weight": point.payload.get("reviewer_weight"),
                        "helpful_votes": point.payload.get("helpful_votes"),
                        "verified_purchase": point.payload.get("verified_purchase"),
                        "relevance_score": round(point.score, 4)
                    }
                    reviews.append(review)
                
                data = {
                    "reviews": reviews,
                    "total_found": len(reviews),
                    "query": query
                }
                
                avg_relevance = sum(r["relevance_score"] for r in reviews) / len(reviews) if reviews else 0
            
            execution_time = (time.time() - start_time) * 1000
            
            return ToolResult(
                tool_name=self.schema.name,
                success=True,
                data=data,
                relevance_score=avg_relevance,
                execution_time_ms=execution_time,
                metadata={
                    "filters_applied": filters is not None or asin is not None,
                    "grouped": group_by_asin,
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
