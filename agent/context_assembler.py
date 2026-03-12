"""agent/context_assembler.py

Dynamic context assembly with token budgeting.
Assembles context based on tool results and relevance scores.
"""

from typing import Any, Dict, List

from agent.tools import ToolResult
from config.settings import MAX_CONTEXT_TOKENS


class ContextAssembler:
    """Assembles context from tool results with dynamic token budgeting."""
    
    def __init__(self, max_tokens: int = MAX_CONTEXT_TOKENS):
        self.max_tokens = max_tokens
        self.reserved_tokens = 500  # Reserve for system prompt and basic info
    
    def allocate_token_budget(
        self,
        tool_results: Dict[str, ToolResult]
    ) -> Dict[str, int]:
        """Allocate token budget based on relevance scores.
        
        Args:
            tool_results: Dict of tool_name -> ToolResult
            
        Returns:
            Dict of tool_name -> allocated_tokens
        """
        available = self.max_tokens - self.reserved_tokens
        
        if not tool_results:
            return {}
        
        # Calculate weighted scores
        weighted_scores = {}
        for tool_name, result in tool_results.items():
            if not result.success:
                weighted_scores[tool_name] = 0
                continue
            
            base_priority = self._get_tool_priority(tool_name)
            weighted_scores[tool_name] = result.relevance_score * base_priority
        
        total_score = sum(weighted_scores.values())
        
        if total_score == 0:
            # Equal distribution if all scores are 0
            per_tool = available // len(tool_results)
            return {name: per_tool for name in tool_results}
        
        # Allocate proportionally
        allocations = {}
        for tool_name, score in weighted_scores.items():
            ratio = score / total_score
            allocations[tool_name] = int(available * ratio)
        
        return allocations
    
    def _get_tool_priority(self, tool_name: str) -> float:
        """Get base priority for a tool."""
        priorities = {
            "semantic_review_search": 1.2,
            "visual_semantic_search": 1.1,
            "knowledge_retrieval": 1.0,
            "semantic_product_search": 0.9,
            "discovery_similar": 0.8,
            "facet_insights": 0.7,
            "recommend_by_example": 0.8,
        }
        return priorities.get(tool_name, 1.0)
    
    def assemble_context(
        self,
        user_query: str,
        current_asin: str,
        product_info: Dict[str, Any],
        tool_results: Dict[str, ToolResult],
        budget: Dict[str, int]
    ) -> str:
        """Assemble final context string.
        
        Args:
            user_query: Original user query
            current_asin: Current product ASIN
            product_info: Basic product information
            tool_results: Tool execution results
            budget: Token budget allocations
            
        Returns:
            Assembled context string
        """
        sections = []
        
        # System prompt
        sections.append(self._build_system_prompt())
        
        # Product basic info
        sections.append(self._build_product_section(product_info))
        
        # Tool results (sorted by budget allocation)
        sorted_tools = sorted(
            budget.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for tool_name, allocated_tokens in sorted_tools:
            if tool_name not in tool_results:
                continue
            
            result = tool_results[tool_name]
            if not result.success or not result.data:
                continue
            
            content = self._format_tool_result(tool_name, result.data)
            
            # Truncate if needed (approx 1 token = 4 chars)
            max_chars = allocated_tokens * 4
            if len(content) > max_chars:
                content = content[:max_chars - 3] + "..."
            
            sections.append(f"[{tool_name.upper()}]\n{content}")
        
        # User context
        sections.append(self._build_user_section(user_query))
        
        return "\n\n".join(sections)
    
    def _build_system_prompt(self) -> str:
        """Build system prompt section."""
        return (
            "[SYSTEM]\n"
            "你是 ShopSense，为视障用户提供的购物助手。用户无法看到商品图片或页面，"
            "你的回答是他们获取商品信息的唯一来源。\n"
            "规则:\n"
            "1. 颜色描述要具体：不说'蓝色'而说'深蓝色，接近牛仔布的蓝色'\n"
            "2. 材质要用触感类比：'像丝绸一样光滑'、'像帆布一样粗糙'\n"
            "3. 尺寸要有参照：不说'大口袋'而说'可以放下智能手机的口袋'\n"
            "4. 先回答最关键的信息\n"
            "5. 控制在4-6句话，因为答案会被朗读\n"
            "6. 绝不说'如图所示'或'从图片可以看出'"
        )
    
    def _build_product_section(self, product_info: Dict[str, Any]) -> str:
        """Build product info section."""
        return (
            f"[PRODUCT]\n"
            f"名称: {product_info.get('name', 'N/A')}\n"
            f"品牌: {product_info.get('brand', 'N/A')}\n"
            f"价格: ${product_info.get('price', 'N/A')}\n"
            f"评分: {product_info.get('rating', 'N/A')}/5\n"
            f"ASIN: {product_info.get('asin', 'N/A')}"
        )
    
    def _format_tool_result(self, tool_name: str, data: Any) -> str:
        """Format tool result data as string."""
        if tool_name == "semantic_review_search":
            return self._format_reviews(data)
        elif tool_name == "knowledge_retrieval":
            return self._format_knowledge(data)
        elif tool_name == "visual_semantic_search":
            return self._format_visual(data)
        elif tool_name == "semantic_product_search":
            return self._format_products(data)
        elif tool_name == "facet_insights":
            return self._format_facet(data)
        elif tool_name == "discovery_similar":
            return self._format_discovery(data)
        elif tool_name == "recommend_by_example":
            return self._format_recommendations(data)
        else:
            return str(data)[:500]
    
    def _format_reviews(self, data: Dict) -> str:
        """Format review search results."""
        reviews = data.get("reviews", [])
        lines = []
        for r in reviews[:5]:
            sentiment_icon = "✓" if r.get("sentiment") == "positive" else "✗" if r.get("sentiment") == "negative" else "·"
            height_info = f" (身高{r['reviewer_height']}cm)" if r.get("reviewer_height") else ""
            lines.append(f'{sentiment_icon} "{r["text"]}"{height_info} [评分:{r["rating"]}]')
        return "\n".join(lines)
    
    def _format_knowledge(self, data: Dict) -> str:
        """Format knowledge results."""
        items = data.get("knowledge_items", [])
        lines = []
        for item in items[:3]:
            content = item.get("content", "")
            if item.get("skin_notes"):
                content += f" 皮肤建议: {item['skin_notes']}"
            if item.get("warmth_range"):
                content += f" 保暖范围: {item['warmth_range']}"
            lines.append(f"- {content}")
        return "\n".join(lines)
    
    def _format_visual(self, data: Dict) -> str:
        """Format visual semantic results."""
        items = data.get("visual_items", [])
        lines = []
        for item in items[:3]:
            desc = item.get("description", "")
            attrs = item.get("attributes", {})
            if attrs.get("color"):
                desc += f" 颜色: {attrs['color']}"
            if attrs.get("style"):
                desc += f" 风格: {attrs['style']}"
            lines.append(f"- {desc}")
        return "\n".join(lines)
    
    def _format_products(self, data: Dict) -> str:
        """Format product search results."""
        products = data.get("products", [])
        lines = []
        for p in products[:3]:
            lines.append(f"- {p['name']} ({p['brand']}) ${p['price']} 评分:{p['rating']}")
        return "\n".join(lines)
    
    def _format_facet(self, data: Dict) -> str:
        """Format facet insights results."""
        distribution = data.get("distribution", {})
        lines = [f"{key}: {count}条" for key, count in distribution.items()]
        return "\n".join(lines)
    
    def _format_discovery(self, data: Dict) -> str:
        """Format discovery results."""
        products = data.get("similar_products", [])
        lines = []
        for p in products[:3]:
            lines.append(f"- {p['name']} ${p['price']} (相似度:{p['similarity_score']})")
        return "\n".join(lines)
    
    def _format_recommendations(self, data: Dict) -> str:
        """Format recommendation results."""
        products = data.get("recommendations", [])
        lines = []
        for p in products[:3]:
            lines.append(f"- {p['name']} ${p['price']} (推荐分:{p['recommendation_score']})")
        return "\n".join(lines)
    
    def _build_user_section(self, user_query: str) -> str:
        """Build user query section."""
        return (
            f"[USER QUESTION]\n"
            f"{user_query}\n\n"
            f"请根据以上信息回答用户问题，控制在4-6句话。"
        )


def assemble_context(
    user_query: str,
    current_asin: str,
    product_info: Dict[str, Any],
    tool_results: Dict[str, ToolResult],
    max_tokens: int = MAX_CONTEXT_TOKENS
) -> str:
    """Convenience function for context assembly."""
    assembler = ContextAssembler(max_tokens=max_tokens)
    budget = assembler.allocate_token_budget(tool_results)
    return assembler.assemble_context(
        user_query, current_asin, product_info, tool_results, budget
    )
