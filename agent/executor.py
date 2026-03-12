"""agent/executor.py

Parallel tool execution engine.
Executes selected tools concurrently using asyncio.
"""

import asyncio
import nest_asyncio
import time
from typing import Any, Dict, List, Optional

from agent.tools import get_tool_instance, ToolResult

# Apply nest_asyncio to allow nested event loops (for Gradio/AnyIO compatibility)
nest_asyncio.apply()


class ToolExecutor:
    """Executes tools in parallel."""
    
    def __init__(self, max_concurrency: int = 5):
        self.max_concurrency = max_concurrency
        self.semaphore = asyncio.Semaphore(max_concurrency)
    
    async def execute_single(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> ToolResult:
        """Execute a single tool with semaphore control.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            
        Returns:
            ToolResult
        """
        async with self.semaphore:
            tool = get_tool_instance(tool_name)
            
            if tool is None:
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    data=None,
                    error_message=f"Tool '{tool_name}' not found",
                    relevance_score=0.0
                )
            
            try:
                result = await tool.execute(**arguments)
                return result
            except Exception as e:
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    data=None,
                    error_message=str(e),
                    relevance_score=0.0
                )
    
    async def execute_batch(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> Dict[str, ToolResult]:
        """Execute multiple tools in parallel.
        
        Args:
            tool_calls: List of {"name": str, "arguments": dict}
            
        Returns:
            Dict mapping tool_name to ToolResult
        """
        if not tool_calls:
            return {}
        
        # Create tasks
        tasks = []
        for tc in tool_calls:
            task = self.execute_single(tc["name"], tc.get("arguments", {}))
            tasks.append(task)
        
        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Map results to tool names
        tool_results = {}
        for i, tc in enumerate(tool_calls):
            result = results[i]
            tool_name = tc["name"]
            
            if isinstance(result, Exception):
                tool_results[tool_name] = ToolResult(
                    tool_name=tool_name,
                    success=False,
                    data=None,
                    error_message=str(result),
                    relevance_score=0.0
                )
            else:
                tool_results[tool_name] = result
        
        return tool_results
    
    def execute_sync(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> Dict[str, ToolResult]:
        """Synchronous wrapper for execute_batch.
        
        Args:
            tool_calls: List of {"name": str, "arguments": dict}
            
        Returns:
            Dict mapping tool_name to ToolResult
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running (Gradio/AnyIO), use run_coroutine_threadsafe
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.execute_batch(tool_calls))
                    return future.result()
            else:
                return loop.run_until_complete(self.execute_batch(tool_calls))
        except RuntimeError:
            # No event loop exists
            return asyncio.run(self.execute_batch(tool_calls))


# Global instance
_executor: Optional[ToolExecutor] = None


def get_executor(max_concurrency: int = 5) -> ToolExecutor:
    """Get global tool executor instance."""
    global _executor
    if _executor is None:
        _executor = ToolExecutor(max_concurrency=max_concurrency)
    return _executor


def execute_tools(tool_calls: List[Dict[str, Any]], **kwargs) -> Dict[str, ToolResult]:
    """Convenience function for executing tools."""
    return get_executor(**kwargs).execute_sync(tool_calls)
