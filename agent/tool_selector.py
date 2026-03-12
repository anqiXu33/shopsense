"""agent/tool_selector.py

Tool selector using LLM Function Calling.
Analyzes user query and selects appropriate tools.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

import requests

from agent.tools import get_all_schemas
from config.settings import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, TEXT_MODEL


SYSTEM_PROMPT = """你是 ShopSense 购物助手。分析用户查询，选择合适的工具获取信息。

可用工具:
1. semantic_product_search - 语义商品搜索
2. semantic_review_search - 语义评价搜索（核心工具，最常用）
3. knowledge_retrieval - 知识检索
4. visual_semantic_search - 视觉语义搜索
5. discovery_similar - 发现相似商品
6. facet_insights - 评价分面统计
7. recommend_by_example - 基于示例推荐

工具选择策略:
- 询问具体使用体验（保暖/尺码/质量）→ semantic_review_search
- 询问材质/敏感肌/保养 → knowledge_retrieval + semantic_review_search
- 询问颜色/外观 → visual_semantic_search
- 找类似商品 → discovery_similar 或 recommend_by_example
- 需要统计 → facet_insights

规则:
- 选择 1-4 个最相关的工具
- 优先使用 semantic_review_search 获取真实反馈
- 每个工具调用必须包含完整参数
- 如果用户提到身高/体重，在 semantic_review_search 中添加 reviewer_height 过滤

输出格式: {"reasoning": "分析过程", "tool_calls": [{"name": "工具名", "arguments": {...}}]}"""


class ToolSelector:
    """Selects tools based on user query using LLM Function Calling."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or DASHSCOPE_API_KEY
        self.base_url = base_url or DASHSCOPE_BASE_URL
        self.model = model or TEXT_MODEL
    
    def select_tools(
        self,
        user_query: str,
        current_asin: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Select tools based on user query.
        
        Args:
            user_query: User's question
            current_asin: Current product ASIN (if any)
            conversation_history: Previous conversation context
            
        Returns:
            Tuple of (reasoning, tool_calls)
        """
        # Build messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add context about current product
        context = ""
        if current_asin:
            context = f"\n当前商品ASIN: {current_asin}"
        
        messages.append({
            "role": "user",
            "content": f"用户查询: {user_query}{context}\n\n请分析并选择工具。只输出JSON格式。"
        })
        
        # Get all tool schemas for function calling
        tools = get_all_schemas()
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "temperature": 0.3,
                    "max_tokens": 500,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            
            message = data["choices"][0]["message"]
            
            # Check if LLM wants to use tools
            tool_calls = []
            reasoning = ""
            
            if "tool_calls" in message:
                for tc in message["tool_calls"]:
                    if tc["type"] == "function":
                        func = tc["function"]
                        tool_calls.append({
                            "name": func["name"],
                            "arguments": json.loads(func["arguments"])
                        })
                reasoning = message.get("content", "选择工具以获取相关信息")
            else:
                # LLM didn't use tools, try to parse content as JSON
                content = message.get("content", "")
                try:
                    parsed = json.loads(content)
                    reasoning = parsed.get("reasoning", "")
                    tool_calls = parsed.get("tool_calls", [])
                except json.JSONDecodeError:
                    reasoning = content
                    # Fallback: default to review search
                    if current_asin:
                        tool_calls = [{
                            "name": "semantic_review_search",
                            "arguments": {
                                "asin": current_asin,
                                "query": user_query,
                                "top_k": 5
                            }
                        }]
            
            # Auto-fill current_asin if not provided in arguments
            if current_asin:
                for tc in tool_calls:
                    args = tc.get("arguments", {})
                    if "asin" in tc.get("arguments", {}) and not args.get("asin"):
                        args["asin"] = current_asin
            
            return reasoning, tool_calls
            
        except Exception as e:
            print(f"[ToolSelector] Error: {e}")
            # Fallback to default tool selection
            fallback_calls = []
            if current_asin:
                fallback_calls = [{
                    "name": "semantic_review_search",
                    "arguments": {
                        "asin": current_asin,
                        "query": user_query,
                        "top_k": 5
                    }
                }]
            return f"Error in tool selection: {e}", fallback_calls


# Global instance
_selector: Optional[ToolSelector] = None


def get_tool_selector():
    """Get global tool selector instance."""
    global _selector
    if _selector is None:
        _selector = ToolSelector()
    return _selector


def select_tools(user_query: str, current_asin: Optional[str] = None, **kwargs):
    """Convenience function for tool selection."""
    return get_tool_selector().select_tools(user_query, current_asin, **kwargs)
