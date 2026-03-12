from __future__ import annotations
"""
agent/agent.py
Main agent loop. Ties everything together:
  intent → plan → execute tools → assemble context → generate answer
"""

import requests
from config.settings import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, TEXT_MODEL
from agent.intent import classify_intent
from agent.planner import get_plan, execute_plan
from agent.context_engineer import assemble_context


def run(user_query: str, product: dict) -> dict:
    """
    Full agent run for a single user query on a single product.

    Returns:
        {
            "answer": str,
            "intent": dict,
            "trace": list,         # tool call trace for UI transparency panel
            "context_preview": str # first 300 chars of assembled context
        }
    """
    print(f"\n{'='*50}")
    print(f"[Agent] Query: {user_query}")

    # Step 1: Classify intent
    intent_result = classify_intent(user_query)
    print(
        f"[Agent] Intent: {intent_result['primary_intent']} | Entities: {intent_result['entities']}"
    )

    # Step 2: Get and execute plan
    plan = get_plan(intent_result["primary_intent"])
    context_for_planner = {
        "product": product,
        "intent_result": intent_result,
        "user_query": user_query,
    }
    tool_results = execute_plan(plan, context_for_planner)
    trace = tool_results.pop("_trace", [])

    # Step 3: Assemble context
    prompt = assemble_context(
        user_query=user_query,
        product=product,
        intent_result=intent_result,
        tool_results=tool_results,
    )
    print(f"[Agent] Context assembled ({len(prompt)} chars)")

    # Step 4: Generate answer via HuggingFace LLM
    answer = generate_answer(prompt, intent_result)

    return {
        "answer": answer,
        "intent": intent_result,
        "trace": trace,
        "context_preview": prompt[:400] + "..." if len(prompt) > 400 else prompt,
    }


def generate_answer(prompt: str, intent_result: "dict | None" = None) -> str:
    if intent_result is None:
        intent_result = {}
    try:
        response = requests.post(
            f"{DASHSCOPE_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": TEXT_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.3,
            },
            timeout=(10, 180),
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[Agent] LLM call failed: {e}. Using mock answer.")
        return "[Demo mode] Set DASHSCOPE_API_KEY in .env to enable real answers."
