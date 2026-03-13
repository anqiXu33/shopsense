from __future__ import annotations
"""
agent/context_engineer.py
Assembles the final LLM prompt from tool results.
This is the core of "Context Engineering" for the hackathon.

Key decisions made here:
  - How many tokens each source gets
  - How to format reviews (structured, not raw)
  - How to flag conflicts between knowledge and reviews
  - What always goes in vs. what's optional
"""

from config.settings import MAX_CONTEXT_TOKENS, TOKEN_BUDGETS


def assemble_context(
    user_query: str,
    product: dict,
    intent_result: dict,
    tool_results: dict,
) -> str:
    """
    Returns a complete prompt string ready to send to the LLM.
    """
    primary_intent = intent_result["primary_intent"]
    entities = intent_result["entities"]
    budget = TOKEN_BUDGETS.get(primary_intent, TOKEN_BUDGETS["default"])

    # ── Always-included sections ──────────────────────────────────────────────
    sections = []

    sections.append(_system_prompt())
    sections.append(_product_section(product))
    sections.append(_visual_section(tool_results))

    # Estimate tokens used so far (rough: 1 token ≈ 4 chars)
    used = sum(len(s) for s in sections) // 4
    remaining = MAX_CONTEXT_TOKENS - used - 200  # 200 reserved for answer

    # ── Budget-allocated sections ─────────────────────────────────────────────
    knowledge_budget = int(remaining * budget.get("knowledge", 0))
    reviews_budget   = int(remaining * budget.get("reviews", 0))
    sizing_budget    = int(remaining * budget.get("sizing", 0))

    if knowledge_budget > 0:
        knowledge_text = _knowledge_section(tool_results, knowledge_budget)
        if knowledge_text:
            sections.append(knowledge_text)

    if reviews_budget > 0:
        reviews_text = _reviews_section(tool_results, reviews_budget)
        if reviews_text:
            sections.append(reviews_text)

    if sizing_budget > 0:
        sizing_text = _sizing_section(tool_results, sizing_budget, entities)
        if sizing_text:
            sections.append(sizing_text)

    # ── Conflict detection ────────────────────────────────────────────────────
    conflict = _detect_conflict(tool_results)
    if conflict:
        sections.append(f"\n⚠️ NOTE FOR ASSISTANT: {conflict}")

    # ── User context + question ───────────────────────────────────────────────
    sections.append(_user_section(user_query, entities))

    return "\n\n".join(filter(None, sections))


# ── Section builders ──────────────────────────────────────────────────────────

def _system_prompt() -> str:
    return (
        "You are ShopSense, a shopping assistant for visually impaired users. "
        "The user CANNOT see any images or the product page. "
        "Your answer is their ONLY source of product information. "
        "Rules:\n"
        "1. Always describe colors with specific references: not 'blue' but "
        "'deep navy blue, similar to dark denim'.\n"
        "2. Describe textures with touch analogies: 'smooth like silk', "
        "'rough like canvas'.\n"
        "3. Give size references: not 'large pocket' but 'pocket large enough "
        "to fit a smartphone'.\n"
        "4. Lead with the most decision-relevant fact.\n"
        "5. Keep answers to 4-5 sentences — this will be read aloud.\n"
        "6. Never say 'as you can see' or 'looking at the image'."
    )

def _product_section(product: dict) -> str:
    return (
        f"PRODUCT: {product['name']} | "
        f"Brand: {product['brand']} | "
        f"Category: {product['category']} | "
        f"Price: ${product['price']}"
    )

def _visual_section(tool_results: dict) -> str:
    for key, val in tool_results.items():
        if key.startswith("visual_analysis") and isinstance(val, dict):
            desc = val.get("description", "")
            if desc and "unavailable" not in desc:
                return f"VISUAL ANALYSIS:\n{desc}"
    return ""

def _knowledge_section(tool_results: dict, budget_tokens: int) -> str:
    entries = []
    for key, val in tool_results.items():
        if key.startswith("search_knowledge") and isinstance(val, list):
            for item in val:
                entries.append(f"- {item['material'].upper()}: {item['text']}")
    if not entries:
        return ""
    text = "MATERIAL KNOWLEDGE:\n" + "\n".join(entries)
    return _truncate(text, budget_tokens)

def _reviews_section(tool_results: dict, budget_tokens: int) -> str:
    all_reviews = []
    for key, val in tool_results.items():
        if key.startswith("search_reviews") and isinstance(val, list):
            all_reviews.extend(val)

    if not all_reviews:
        return ""

    positive = [r for r in all_reviews if r.get("sentiment") == "positive"]
    negative = [r for r in all_reviews if r.get("sentiment") == "negative"]
    neutral  = [r for r in all_reviews if r.get("sentiment") == "neutral"]

    lines = ["BUYER REVIEWS (real feedback):"]
    if positive:
        lines.append("Positive:")
        for r in positive[:3]:
            h = f" (reviewer: {r['reviewer_height']}cm)" if r.get("reviewer_height") else ""
            lines.append(f'  ✓ "{r["text"]}"{h}')
    if negative:
        lines.append("Concerns:")
        for r in negative[:3]:
            h = f" (reviewer: {r['reviewer_height']}cm)" if r.get("reviewer_height") else ""
            lines.append(f'  ✗ "{r["text"]}"{h}')
    if neutral:
        lines.append("Neutral notes:")
        for r in neutral[:2]:
            lines.append(f'  · "{r["text"]}"')

    return _truncate("\n".join(lines), budget_tokens)

def _sizing_section(tool_results: dict, budget_tokens: int, entities: dict) -> str:
    entries = []
    for key, val in tool_results.items():
        if key.startswith("search_sizing") and isinstance(val, list):
            for s in val:
                entries.append(f"  Size {s['size_label']}: {s['size_range']}")

    if not entries:
        return ""

    lines = ["SIZING GUIDE:"]
    if entities.get("height") or entities.get("weight"):
        lines.append(
            f"User measurements: "
            f"{'height ' + str(entities['height']) + 'cm' if entities.get('height') else ''} "
            f"{'weight ' + str(entities['weight']) + 'kg' if entities.get('weight') else ''}"
        )
    lines.extend(entries)
    return _truncate("\n".join(lines), budget_tokens)

def _user_section(query: str, entities: dict) -> str:
    parts = [f"USER QUESTION: {query}"]
    user_context = []
    if entities.get("skin_condition"):
        user_context.append(f"skin condition: {entities['skin_condition']}")
    if entities.get("temperature"):
        user_context.append(f"target temperature: {entities['temperature']}°C")
    if user_context:
        parts.append("User context: " + ", ".join(user_context))
    parts.append(
        "Please answer in 4-6 sentences. "
        "Be specific. This answer will be read aloud to a visually impaired user."
    )
    return "\n".join(parts)

def _detect_conflict(tool_results: dict) -> str | None:
    """
    Simple conflict detection: if knowledge says one thing and reviews contradict.
    Returns a warning string or None.
    """
    # Check warmth conflict: knowledge boundary vs review sentiment
    knowledge_texts = []
    for key, val in tool_results.items():
        if key.startswith("search_knowledge") and isinstance(val, list):
            knowledge_texts.extend([i["text"] for i in val])

    review_texts = []
    for key, val in tool_results.items():
        if key.startswith("search_reviews") and isinstance(val, list):
            review_texts.extend([r["text"] for r in val])

    k_text = " ".join(knowledge_texts).lower()
    r_text = " ".join(review_texts).lower()

    if ("not warm enough" in r_text or "too cold" in r_text) and "warm" in k_text:
        return (
            "Some reviewers report insufficient warmth, while material specs suggest "
            "adequate insulation. Present both perspectives to the user."
        )
    return None

def _truncate(text: str, max_tokens: int) -> str:
    """Rough truncation: 1 token ≈ 4 characters."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."
