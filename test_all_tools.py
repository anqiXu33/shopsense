#!/usr/bin/env python3
"""
test_all_tools.py - Comprehensive test for all ShopSense tools

Tests all 7 tools:
1. semantic_product_search
2. semantic_review_search
3. knowledge_retrieval
4. visual_semantic_search
5. discovery_similar
6. facet_insights
7. recommend_by_example
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.tools import get_tool_instance, list_tools
from agent.executor import execute_tools


def print_header(title):
    print("\n" + "="*70)
    print(f" {title}")
    print("="*70)


def print_result(tool_name, result):
    if result.success:
        print(f"✅ {tool_name}")
        print(f"   Score: {result.relevance_score:.3f}")
        print(f"   Time: {result.execution_time_ms:.1f}ms")
        if result.data:
            print(f"   Data: {list(result.data.keys())}")
    else:
        print(f"❌ {tool_name}")
        print(f"   Error: {result.error_message}")


def test_semantic_product_search():
    print_header("Test 1: semantic_product_search")
    
    tool = get_tool_instance("semantic_product_search")
    result = asyncio.run(tool.execute(
        query="保暖羽绒服",
        filters={"price_max": 200},
        top_k=3
    ))
    
    print_result("semantic_product_search", result)
    
    if result.success and result.data:
        products = result.data.get("products", [])
        print(f"   Found {len(products)} products:")
        for p in products[:3]:
            print(f"      - {p['name']} (${p['price']})")
    
    return result.success


def test_semantic_review_search():
    print_header("Test 2: semantic_review_search")
    
    tool = get_tool_instance("semantic_review_search")
    result = asyncio.run(tool.execute(
        query="保暖性怎么样",
        asin="P001",
        filters={
            "reviewer_height_min": 165,
            "reviewer_height_max": 175
        },
        top_k=3
    ))
    
    print_result("semantic_review_search", result)
    
    if result.success and result.data:
        reviews = result.data.get("reviews", [])
        print(f"   Found {len(reviews)} reviews:")
        for r in reviews[:2]:
            height = f" (身高{r['reviewer_height']}cm)" if r.get('reviewer_height') else ""
            print(f"      - \"{r['text'][:50]}...\"{height} [评分:{r['rating']}]")
    
    return result.success


def test_knowledge_retrieval():
    print_header("Test 3: knowledge_retrieval")
    
    tool = get_tool_instance("knowledge_retrieval")
    result = asyncio.run(tool.execute(
        query="羽绒保暖性",
        material="duck_down",
        topic="warmth",
        top_k=2
    ))
    
    print_result("knowledge_retrieval", result)
    
    if result.success and result.data:
        items = result.data.get("knowledge_items", [])
        print(f"   Found {len(items)} knowledge items:")
        for item in items[:2]:
            print(f"      - {item['material']}: {item['content'][:60]}...")
    
    return result.success


def test_visual_semantic_search():
    print_header("Test 4: visual_semantic_search")
    
    tool = get_tool_instance("visual_semantic_search")
    result = asyncio.run(tool.execute(
        asin="P001",
        query="颜色",
        top_k=2
    ))
    
    print_result("visual_semantic_search", result)
    
    if result.success and result.data:
        items = result.data.get("visual_items", [])
        print(f"   Found {len(items)} visual items:")
        for item in items[:2]:
            print(f"      - {item['description'][:60]}...")
    
    return result.success


def test_discovery_similar():
    print_header("Test 5: discovery_similar")
    
    tool = get_tool_instance("discovery_similar")
    result = asyncio.run(tool.execute(
        target_asin="P001",
        context="保暖性",
        top_k=3
    ))
    
    print_result("discovery_similar", result)
    
    if result.success and result.data:
        products = result.data.get("similar_products", [])
        print(f"   Found {len(products)} similar products:")
        for p in products[:3]:
            print(f"      - {p['name']} (相似度: {p['similarity_score']})")
    
    return result.success


def test_facet_insights():
    print_header("Test 6: facet_insights")
    
    tool = get_tool_instance("facet_insights")
    result = asyncio.run(tool.execute(
        asin="P001",
        facet_key="rating"
    ))
    
    print_result("facet_insights", result)
    
    if result.success and result.data:
        distribution = result.data.get("distribution", {})
        print(f"   Rating distribution:")
        for rating, count in sorted(distribution.items()):
            print(f"      {rating} stars: {count} reviews")
    
    return result.success


def test_recommend_by_example():
    print_header("Test 7: recommend_by_example")
    
    tool = get_tool_instance("recommend_by_example")
    result = asyncio.run(tool.execute(
        positive_asins=["P001"],
        limit=3
    ))
    
    print_result("recommend_by_example", result)
    
    if result.success and result.data:
        products = result.data.get("recommendations", [])
        print(f"   Found {len(products)} recommendations:")
        for p in products[:3]:
            print(f"      - {p['name']} (推荐分: {p['recommendation_score']})")
    
    return result.success


def test_parallel_execution():
    print_header("Test 8: Parallel Tool Execution")
    
    tool_calls = [
        {"name": "semantic_product_search", "arguments": {"query": "羽绒服", "top_k": 2}},
        {"name": "semantic_review_search", "arguments": {"asin": "P001", "query": "保暖", "top_k": 2}},
        {"name": "knowledge_retrieval", "arguments": {"query": "保暖性", "top_k": 2}},
    ]
    
    print(f"Executing {len(tool_calls)} tools in parallel...")
    results = execute_tools(tool_calls)
    
    all_success = True
    for name, result in results.items():
        status = "✅" if result.success else "❌"
        print(f"   {status} {name}: score={result.relevance_score:.3f}")
        if not result.success:
            all_success = False
    
    return all_success


def run_all_tests():
    print("\n" + "🛍️  ShopSense Tool Test Suite".center(70))
    print("="*70)
    
    # Check available tools
    tools = list_tools()
    print(f"\nAvailable tools ({len(tools)}):")
    for t in tools:
        print(f"   - {t}")
    
    # Run tests
    results = []
    
    results.append(("semantic_product_search", test_semantic_product_search()))
    results.append(("semantic_review_search", test_semantic_review_search()))
    results.append(("knowledge_retrieval", test_knowledge_retrieval()))
    results.append(("visual_semantic_search", test_visual_semantic_search()))
    results.append(("discovery_similar", test_discovery_similar()))
    results.append(("facet_insights", test_facet_insights()))
    results.append(("recommend_by_example", test_recommend_by_example()))
    results.append(("parallel_execution", test_parallel_execution()))
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {name}")
    
    print(f"\n   Total: {len(results)} tests")
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    
    print("\n" + "="*70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
