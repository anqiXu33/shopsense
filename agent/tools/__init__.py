"""agent/tools/__init__.py

Tool implementations for ShopSense agent.
"""

from agent.tools.base import (
    BaseTool,
    ToolResult,
    ToolSchema,
    register_tool,
    get_tool,
    get_tool_instance,
    get_all_tools,
    get_all_schemas,
    list_tools,
)

# Import all tools to register them
from agent.tools.product_search import SemanticProductSearchTool
from agent.tools.review_search import SemanticReviewSearchTool
from agent.tools.knowledge import KnowledgeRetrievalTool
from agent.tools.visual import VisualSemanticSearchTool
from agent.tools.discovery import DiscoverySimilarTool
from agent.tools.facet import FacetInsightsTool
from agent.tools.recommend import RecommendByExampleTool

__all__ = [
    # Base classes
    "BaseTool",
    "ToolResult",
    "ToolSchema",
    "register_tool",
    "get_tool",
    "get_tool_instance",
    "get_all_tools",
    "get_all_schemas",
    "list_tools",
    # Tool classes
    "SemanticProductSearchTool",
    "SemanticReviewSearchTool",
    "KnowledgeRetrievalTool",
    "VisualSemanticSearchTool",
    "DiscoverySimilarTool",
    "FacetInsightsTool",
    "RecommendByExampleTool",
]
