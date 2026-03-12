"""agent/tools/knowledge.py

Knowledge retrieval tool for material properties and care instructions.
"""

import time
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from agent.tools.base import BaseTool, ToolResult, ToolSchema, register_tool
from core.embeddings import embed
from config.settings import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTIONS


@register_tool
class KnowledgeRetrievalTool(BaseTool):
    """Tool for retrieving professional knowledge about materials, sizing, and care."""
    
    schema = ToolSchema(
        name="knowledge_retrieval",
        description="检索专业知识库。查询材料特性、保暖性、皮肤兼容性、尺码标准、保养建议。当需要专业背景知识回答材质、保养、敏感肌等问题时使用。",
        parameters={
            "query": {
                "type": "string",
                "description": "查询主题，如'650FP羽绒保暖性'、'羊毛过敏'、'尺码换算'"
            },
            "material": {
                "type": "string",
                "description": "具体材料名称，如'down'、'wool'、'cotton'"
            },
            "topic": {
                "type": "string",
                "enum": ["material", "warmth", "skin", "sizing", "care", "general"],
                "description": "知识类别"
            },
            "top_k": {
                "type": "integer",
                "default": 3,
                "description": "返回知识条目数量"
            }
        },
        required=["query"]
    )
    
    def __init__(self):
        super().__init__()
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        self.collection_name = QDRANT_COLLECTIONS["knowledge"]
    
    async def execute(
        self,
        query: str,
        material: Optional[str] = None,
        topic: Optional[str] = None,
        top_k: int = 3
    ) -> ToolResult:
        """Execute knowledge retrieval."""
        start_time = time.time()
        
        try:
            # Generate embedding
            vector = embed(query)
            
            # Build filter conditions
            must_conditions = []
            
            if material:
                must_conditions.append(
                    FieldCondition(key="material", match=MatchValue(value=material))
                )
            
            if topic and topic != "general":
                must_conditions.append(
                    FieldCondition(key="topic", match=MatchValue(value=topic))
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
            knowledge_items = []
            for point in results.points:
                item = {
                    "material": point.payload.get("material"),
                    "topic": point.payload.get("topic"),
                    "category": point.payload.get("category"),
                    "content": point.payload.get("content"),
                    "properties": point.payload.get("properties", ""),
                    "skin_notes": point.payload.get("skin_notes", ""),
                    "warmth_range": point.payload.get("warmth_range", ""),
                    "care_instructions": point.payload.get("care_instructions", ""),
                    "source": point.payload.get("source", ""),
                    "relevance_score": round(point.score, 4)
                }
                knowledge_items.append(item)
            
            execution_time = (time.time() - start_time) * 1000
            
            avg_relevance = sum(k["relevance_score"] for k in knowledge_items) / len(knowledge_items) if knowledge_items else 0
            
            return ToolResult(
                tool_name=self.schema.name,
                success=True,
                data={
                    "knowledge_items": knowledge_items,
                    "total_found": len(knowledge_items),
                    "query": query
                },
                relevance_score=avg_relevance,
                execution_time_ms=execution_time,
                metadata={
                    "filters_applied": material is not None or topic is not None,
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
