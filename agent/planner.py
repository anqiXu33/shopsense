"""
agent/planner.py
DAG-based planner: decides which tools to call given an intent.
Each plan is an ordered list of (tool_name, kwargs_builder) tuples.
"""

from agent.tools import visual_analysis, search_knowledge, search_reviews, search_sizing

# Each entry: (tool_fn, fn that builds kwargs from context)
# context = {"product": {...}, "intent_result": {...}}

PLANS = {
    "appearance_inquiry": [
        ("visual_analysis", lambda ctx: {
            "image_url": ctx["product"]["image_url"]
        }),
        ("search_reviews", lambda ctx: {
            "query": "color appearance design look",
            "product_id": ctx["product"]["id"],
            "top_k": 3
        }),
    ],
    "warmth_inquiry": [
        ("visual_analysis", lambda ctx: {
            "image_url": ctx["product"]["image_url"],
            "question": "What fill material and fill weight is visible? Describe the insulation."
        }),
        ("search_knowledge", lambda ctx: {
            "query": f"warmth temperature {ctx['product']['description']}"
        }),
        ("search_reviews", lambda ctx: {
            "query": "warm cold temperature degrees winter",
            "product_id": ctx["product"]["id"],
        }),
    ],
    "material_sensitivity": [
        ("visual_analysis", lambda ctx: {
            "image_url": ctx["product"]["image_url"],
            "question": "What material is this product made from? Describe texture and feel."
        }),
        ("search_knowledge", lambda ctx: {
            "query": f"skin sensitive allergy {ctx['product']['description']}"
        }),
        ("search_reviews", lambda ctx: {
            "query": "sensitive skin itch scratch allergy soft feel",
            "product_id": ctx["product"]["id"],
        }),
    ],
    "size_fitting": [
        ("search_sizing", lambda ctx: {
            "product_id": ctx["product"]["id"],
            "height": ctx["intent_result"]["entities"].get("height"),
            "weight": ctx["intent_result"]["entities"].get("weight"),
        }),
        ("search_reviews", lambda ctx: {
            "query": "size fit runs small large true to size",
            "product_id": ctx["product"]["id"],
            "reviewer_height_min": (ctx["intent_result"]["entities"].get("height") or 170) - 7,
            "reviewer_height_max": (ctx["intent_result"]["entities"].get("height") or 170) + 7,
        }),
    ],
    "review_summary": [
        ("search_reviews", lambda ctx: {
            "query": ctx.get("user_query", "product quality"),
            "product_id": ctx["product"]["id"],
            "sentiment": "negative",
            "top_k": 5
        }),
        ("search_reviews", lambda ctx: {
            "query": ctx.get("user_query", "product quality"),
            "product_id": ctx["product"]["id"],
            "sentiment": "positive",
            "top_k": 5
        }),
    ],
    "usage_context": [
        ("visual_analysis", lambda ctx: {
            "image_url": ctx["product"]["image_url"]
        }),
        ("search_knowledge", lambda ctx: {
            "query": f"usage occasion suitable for {ctx['product']['category']}"
        }),
        ("search_reviews", lambda ctx: {
            "query": ctx.get("user_query", "usage occasion wear"),
            "product_id": ctx["product"]["id"],
        }),
    ],
}

def get_plan(intent: str) -> list:
    """Return the tool call plan for a given intent."""
    return PLANS.get(intent, PLANS["appearance_inquiry"])


def execute_plan(plan: list, context: dict) -> dict:
    """
    Execute each step in the plan.
    Returns a dict of tool_name → result.
    """
    tool_fns = {
        "visual_analysis": visual_analysis,
        "search_knowledge": search_knowledge,
        "search_reviews": search_reviews,
        "search_sizing": search_sizing,
    }

    results = {}
    trace = []  # for the UI transparency panel

    for tool_name, kwargs_builder in plan:
        kwargs = kwargs_builder(context)
        print(f"  [Planner] Calling {tool_name} with {list(kwargs.keys())}")

        try:
            result = tool_fns[tool_name](**kwargs)
            key = f"{tool_name}_{len([k for k in results if k.startswith(tool_name)])}"
            results[key] = result
            trace.append({
                "tool": tool_name,
                "kwargs_keys": list(kwargs.keys()),
                "result_count": len(result) if isinstance(result, list) else 1,
                "status": "success"
            })
        except Exception as e:
            print(f"  [Planner] {tool_name} failed: {e}")
            trace.append({"tool": tool_name, "status": "failed", "error": str(e)})

    results["_trace"] = trace
    return results
