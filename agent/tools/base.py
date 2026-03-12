"""agent/tools/base.py

Base class and registry for tools.
All tools must inherit from BaseTool and be registered with @register_tool.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ToolResult:
    """Result from a tool execution."""
    tool_name: str
    success: bool
    data: Any
    relevance_score: float = 0.0
    error_message: Optional[str] = None
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "data": self.data,
            "relevance_score": self.relevance_score,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }


@dataclass
class ToolSchema:
    """Schema definition for a tool (OpenAI Function Calling format)."""
    name: str
    description: str
    parameters: Dict[str, Any]
    required: List[str]
    
    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI function format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }


class BaseTool(ABC):
    """Base class for all tools.
    
    All tools must:
    1. Inherit from BaseTool
    2. Define schema class attribute
    3. Implement execute method
    4. Be decorated with @register_tool
    """
    
    schema: ToolSchema
    
    def __init__(self):
        """Initialize tool."""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters.
        
        Args:
            **kwargs: Parameters as defined in schema
            
        Returns:
            ToolResult with execution results
        """
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema in OpenAI format."""
        return self.schema.to_openai_format()
    
    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate parameters against schema.
        
        Args:
            params: Parameters to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required parameters
        for required_param in self.schema.required:
            if required_param not in params:
                return False, f"Missing required parameter: {required_param}"
        
        return True, None


# Global tool registry
_TOOL_REGISTRY: Dict[str, Type[BaseTool]] = {}
_TOOL_SCHEMAS: Dict[str, ToolSchema] = {}


def register_tool(cls: Type[BaseTool]) -> Type[BaseTool]:
    """Decorator to register a tool class.
    
    Usage:
        @register_tool
        class MyTool(BaseTool):
            schema = ToolSchema(...)
            ...
    """
    tool_name = cls.schema.name
    
    if tool_name in _TOOL_REGISTRY:
        raise ValueError(f"Tool '{tool_name}' is already registered")
    
    _TOOL_REGISTRY[tool_name] = cls
    _TOOL_SCHEMAS[tool_name] = cls.schema
    
    return cls


def get_tool(name: str) -> Optional[Type[BaseTool]]:
    """Get tool class by name."""
    return _TOOL_REGISTRY.get(name)


def get_tool_instance(name: str) -> Optional[BaseTool]:
    """Get tool instance by name."""
    tool_cls = _TOOL_REGISTRY.get(name)
    if tool_cls:
        return tool_cls()
    return None


def get_all_tools() -> Dict[str, Type[BaseTool]]:
    """Get all registered tools."""
    return _TOOL_REGISTRY.copy()


def get_all_schemas() -> List[Dict[str, Any]]:
    """Get all tool schemas in OpenAI format."""
    return [schema.to_openai_format() for schema in _TOOL_SCHEMAS.values()]


def list_tools() -> List[str]:
    """List all registered tool names."""
    return list(_TOOL_REGISTRY.keys())


def clear_registry():
    """Clear all registered tools (mainly for testing)."""
    _TOOL_REGISTRY.clear()
    _TOOL_SCHEMAS.clear()
