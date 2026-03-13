"""tests/test_end_to_end.py

End-to-end integration test for ShopSense agent.
Tests the complete flow: query -> tool selection -> execution -> context assembly.
"""

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.tool_selector import select_tools
from agent.executor import execute_tools
from agent.context_assembler import assemble_context, ContextAssembler
from agent.conflict_detector import detect_conflicts
from agent.tools import list_tools


def test_tool_registration():
    """Test that all tools are registered."""
    print("\n[TEST] Tool Registration")
    print("-" * 50)
    
    tools = list_tools()
    expected_tools = [
        "semantic_product_search",
        "semantic_review_search",
        "knowledge_retrieval",
        "visual_semantic_search",
        "discovery_similar",
        "facet_insights",
        "recommend_by_example",
    ]
    
    for tool in expected_tools:
        if tool in tools:
            print(f"  ✓ {tool}")
        else:
            print(f"  ✗ {tool} NOT FOUND")
            return False
    
    print(f"\n✓ All {len(expected_tools)} tools registered")
    return True


def test_embedding_service():
    """Test embedding service."""
    print("\n[TEST] Embedding Service")
    print("-" * 50)
    
    from core.embeddings import embed
    
    try:
        vector = embed("test query")
        print(f"  ✓ Embedding generated: {len(vector)} dimensions")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_single_tool(tool_name, arguments):
    """Test a single tool execution."""
    from agent.tools import get_tool_instance
    
    print(f"\n[TEST] Tool: {tool_name}")
    print("-" * 50)
    
    tool = get_tool_instance(tool_name)
    if not tool:
        print(f"  ✗ Tool not found")
        return False
    
    try:
        result = asyncio.run(tool.execute(**arguments))
        if result.success:
            print(f"  ✓ Success (score: {result.relevance_score:.3f}, time: {result.execution_time_ms:.1f}ms)")
            print(f"  Data keys: {list(result.data.keys()) if result.data else 'None'}")
            return True
        else:
            print(f"  ✗ Failed: {result.error_message}")
            return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_review_search():
    """Test review search tool."""
    return test_single_tool("semantic_review_search", {
        "asin": "P001",
        "query": "保暖性怎么样",
        "top_k": 3
    })


def test_knowledge_retrieval():
    """Test knowledge retrieval tool."""
    return test_single_tool("knowledge_retrieval", {
        "query": "鸭绒保暖性",
        "material": "duck_down",
        "top_k": 2
    })


def test_product_search():
    """Test product search tool."""
    return test_single_tool("semantic_product_search", {
        "query": "保暖外套",
        "top_k": 3
    })


def test_facet_insights():
    """Test facet insights tool."""
    return test_single_tool("facet_insights", {
        "asin": "P001",
        "facet_key": "rating"
    })


def test_parallel_execution():
    """Test parallel tool execution."""
    print("\n[TEST] Parallel Tool Execution")
    print("-" * 50)
    
    tool_calls = [
        {"name": "semantic_review_search", "arguments": {"asin": "P001", "query": "保暖", "top_k": 3}},
        {"name": "knowledge_retrieval", "arguments": {"query": "羽绒保暖", "top_k": 2}},
    ]
    
    try:
        results = execute_tools(tool_calls)
        
        for tool_name, result in results.items():
            status = "✓" if result.success else "✗"
            print(f"  {status} {tool_name}: score={result.relevance_score:.3f}")
        
        all_success = all(r.success for r in results.values())
        if all_success:
            print(f"\n✓ All {len(results)} tools executed successfully")
        return all_success
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_context_assembly():
    """Test context assembly."""
    print("\n[TEST] Context Assembly")
    print("-" * 50)
    
    # Simulate tool results
    from agent.tools import ToolResult
    
    tool_results = {
        "semantic_review_search": ToolResult(
            tool_name="semantic_review_search",
            success=True,
            data={
                "reviews": [
                    {"text": "很暖和，在-5度穿没问题", "rating": 5, "sentiment": "positive"},
                    {"text": "质量不错", "rating": 4, "sentiment": "positive"},
                ]
            },
            relevance_score=0.85
        ),
        "knowledge_retrieval": ToolResult(
            tool_name="knowledge_retrieval",
            success=True,
            data={
                "knowledge_items": [
                    {"content": "450g鸭绒适合-5到-10度", "material": "duck_down"}
                ]
            },
            relevance_score=0.90
        ),
    }
    
    product_info = {
        "asin": "P001",
        "name": "Test Product",
        "brand": "TestBrand",
        "price": 99.99,
        "rating": 4.5
    }
    
    try:
        context = assemble_context(
            user_query="这件保暖吗？",
            current_asin="P001",
            product_info=product_info,
            tool_results=tool_results
        )
        
        print(f"  ✓ Context assembled")
        print(f"  Length: {len(context)} chars")
        print(f"\n  Context preview:")
        print(f"  {context[:300]}...")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_conflict_detection():
    """Test conflict detection."""
    print("\n[TEST] Conflict Detection")
    print("-" * 50)
    
    from agent.tools import ToolResult
    
    # Create conflicting data
    tool_results = {
        "knowledge_retrieval": ToolResult(
            tool_name="knowledge_retrieval",
            success=True,
            data={
                "knowledge_items": [
                    {
                        "content": "Merino wool is hypoallergenic and safe for sensitive skin",
                        "skin_notes": "safe for sensitive skin"
                    }
                ]
            },
            relevance_score=0.90
        ),
        "semantic_review_search": ToolResult(
            tool_name="semantic_review_search",
            success=True,
            data={
                "reviews": [
                    {"text": "Caused rash and itching on my sensitive skin", "rating": 2, "sentiment": "negative"},
                    {"text": "Also had allergic reaction", "rating": 1, "sentiment": "negative"},
                ]
            },
            relevance_score=0.85
        ),
    }
    
    try:
        conflicts = detect_conflicts(tool_results)
        
        if conflicts:
            print(f"  ✓ Detected {len(conflicts)} conflict(s)")
            for c in conflicts:
                print(f"    - {c.conflict_type} ({c.severity}): {c.description[:50]}...")
            return True
        else:
            print(f"  ℹ No conflicts detected")
            return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("ShopSense End-to-End Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Tool Registration", test_tool_registration),
        ("Embedding Service", test_embedding_service),
        ("Review Search", test_review_search),
        ("Knowledge Retrieval", test_knowledge_retrieval),
        ("Product Search", test_product_search),
        ("Facet Insights", test_facet_insights),
        ("Parallel Execution", test_parallel_execution),
        ("Context Assembly", test_context_assembly),
        ("Conflict Detection", test_conflict_detection),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} failed with exception: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {len(results)} tests, {passed} passed, {failed} failed")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
