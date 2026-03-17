"""
agent/legacy.py

Legacy single-pass pipeline (preserved for A/B comparison with the ReAct agent).
Called by the /api/query_legacy endpoint.

Architecture:
    1. Rule-based + LLM intent classification  → select tools + limits
    2. Parallel Qdrant search                  → reviews, knowledge, visual
    3. Retrieval reflection                    → confidence, fallback trigger
    4. Context assembly (primary source first) → ordered text sections
    5. Single LLM call                         → answer

Entry point: run_legacy_query(req, client) -> dict
"""

import asyncio
import json
import os
import time

import requests as req_lib
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from config.settings import QDRANT_COLLECTIONS
from core.embeddings import embed
from agent.react import _first_sentence, _CONFLICT_PAIRS


# ── Intent Classification ─────────────────────────────────────────────────────

_BREVITY = (
    "Reply in 2-3 sentences maximum — the user is listening via text-to-speech. "
    "Lead with the direct answer, then one supporting detail. No bullet points or headers."
)

INTENT_RULES = [
    (
        {"warm", "cold", "temperature", "degree", "winter", "freeze", "weather", "arctic", "-10", "-15", "-20"},
        ["review_search", "knowledge_search"],
        "Temperature question — searching reviews and expert knowledge on insulation",
        {
            "primary": "knowledge_search",
            "limits": {"review_search": 3, "knowledge_search": 3},
            "focus": (
                "State the temperature range this product is rated for, then confirm with one customer experience. "
                + _BREVITY
            ),
        },
    ),
    (
        {"skin", "sensitive", "itch", "allerg", "rash", "irritat", "eczema", "dermatit", "react"},
        ["review_search", "knowledge_search"],
        "Skin sensitivity question — searching reviews and material knowledge",
        {
            "primary": "knowledge_search",
            "limits": {"review_search": 3, "knowledge_search": 3},
            "focus": (
                "Give a yes/no verdict on skin safety, then cite the material reason. "
                + _BREVITY
            ),
        },
    ),
    (
        {"color", "colour", "look", "appear", "visual", "describe", "photo", "image", "shade", "tone"},
        ["visual_search", "review_search"],
        "Appearance question — searching visual descriptions and color reviews",
        {
            "primary": "visual_search",
            "limits": {"visual_search": 1, "review_search": 2},
            "focus": (
                "Describe the color and silhouette in one vivid sentence using everyday comparisons. "
                "Add one texture or feature detail. Use plain language for someone who cannot see the image. "
                + _BREVITY
            ),
        },
    ),
    (
        {"size", "sizing", "fit", "fitting", "height", "tall", "small", "large", "tight", "loose", "shrink"},
        ["review_search"],
        "Sizing question — searching customer reviews for fit and sizing feedback",
        {
            "primary": "review_search",
            "limits": {"review_search": 6},
            "focus": (
                "Give the sizing verdict in one phrase (runs small / true to size / runs large), "
                "then state whether to size up or down and why. "
                + _BREVITY
            ),
        },
    ),
    (
        {"price", "cost", "worth", "value", "cheap", "expensive", "afford", "budget"},
        ["review_search", "knowledge_search"],
        "Value question — searching reviews and knowledge for quality-price assessment",
        {
            "primary": "review_search",
            "limits": {"review_search": 3, "knowledge_search": 2},
            "focus": (
                "Give a direct worth-it or not verdict, then cite the main reason from material quality or customer feedback. "
                + _BREVITY
            ),
        },
    ),
    (
        {"wash", "care", "clean", "laundry", "dry", "iron", "maintain", "last", "durable", "wear"},
        ["knowledge_search", "review_search"],
        "Care/durability question — searching expert care guides and reviews",
        {
            "primary": "knowledge_search",
            "limits": {"knowledge_search": 3, "review_search": 2},
            "focus": (
                "Give the two most important care steps (wash temperature, drying method). "
                "Add one durability note if available. "
                + _BREVITY
            ),
        },
    ),
]

_DEFAULT_INTENT = {
    "primary": "review_search",
    "limits": {"review_search": 3, "knowledge_search": 2, "visual_search": 1},
    "focus": "Answer directly and concisely. " + _BREVITY,
}

_SECTION_ORDER = {
    "knowledge_search": ["knowledge", "reviews", "visual"],
    "visual_search":    ["visual", "reviews", "knowledge"],
    "review_search":    ["reviews", "knowledge", "visual"],
}


def select_tools(question: str):
    """Multi-intent: collect all matching rules, merge tools and limits."""
    q = question.lower()
    matched = [
        (tools, reasoning, intent)
        for keywords, tools, reasoning, intent in INTENT_RULES
        if any(kw in q for kw in keywords)
    ]
    if not matched:
        return (
            ["review_search", "knowledge_search", "visual_search"],
            "General question — searching all available sources",
            _DEFAULT_INTENT,
        )

    all_tools = list(dict.fromkeys(t for tools, _, _ in matched for t in tools))

    merged_limits = {}
    for _, _, intent in matched:
        for src, n in intent["limits"].items():
            merged_limits[src] = max(merged_limits.get(src, 0), n)

    primary = matched[0][2]["primary"]
    per_intent = " ".join(
        intent["focus"].replace(_BREVITY, "").strip()
        for _, _, intent in matched
    )
    focus = per_intent + " " + _BREVITY

    reasoning = " + ".join(r for _, r, _ in matched)
    return all_tools, reasoning, {"primary": primary, "limits": merged_limits, "focus": focus}


# ── LLM Tool Selection ────────────────────────────────────────────────────────

_TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "review_search",
            "description": (
                "Search customer reviews for this product. "
                "Use for: sizing/fit feedback, durability reports, real-world usage experience, "
                "value-for-money opinions, skin reactions reported by actual users."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of reviews to retrieve (1–8). Use more when aggregating opinions.",
                        "minimum": 1,
                        "maximum": 8,
                    },
                    "focus": {
                        "type": "string",
                        "description": "One-sentence instruction guiding how to use these reviews in the final answer.",
                    },
                },
                "required": ["limit", "focus"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_search",
            "description": (
                "Search an expert fabric and material knowledge base. "
                "Use for: temperature/insulation ratings, material properties (hypoallergenic, waterproof, "
                "breathability), care instructions, technical certifications."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of knowledge entries to retrieve (1–5).",
                        "minimum": 1,
                        "maximum": 5,
                    },
                    "focus": {
                        "type": "string",
                        "description": "One-sentence instruction guiding how to use this knowledge in the final answer.",
                    },
                },
                "required": ["limit", "focus"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "visual_search",
            "description": (
                "Search visual/image descriptions of the product. "
                "Use for: color, appearance, silhouette, texture, design details, "
                "what the product looks like for someone who cannot see the image."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of visual descriptions to retrieve (1–2).",
                        "minimum": 1,
                        "maximum": 2,
                    },
                    "focus": {
                        "type": "string",
                        "description": "One-sentence instruction guiding how to use this visual description.",
                    },
                },
                "required": ["limit", "focus"],
            },
        },
    },
]

_TOOL_SELECTION_SYSTEM = (
    "You are a retrieval-planning agent for a shopping assistant. "
    "Given a user question about a product, call one or more search tools to retrieve "
    "the most relevant information. Rules:\n"
    "- Call multiple tools when the question spans multiple topics.\n"
    "- Set `limit` based on how many results you actually need (don't over-fetch).\n"
    "- Set `focus` to a concise instruction that guides how the final answer should use "
    "the retrieved results (e.g. 'Give a sizing verdict: runs small/true/large').\n"
    "- The first tool you call becomes the primary source for the answer."
)


async def select_tools_llm(question: str):
    """LLM function-calling tool selection. Falls back to rule-based on error."""
    base_url = os.getenv("DASHSCOPE_BASE_URL", "https://api.groq.com/openai/v1")
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("HF_API_KEY")
    model = os.getenv("TEXT_MODEL", "llama-3.3-70b-versatile")

    try:
        resp = await asyncio.to_thread(
            req_lib.post,
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _TOOL_SELECTION_SYSTEM},
                    {"role": "user", "content": question},
                ],
                "tools": _TOOL_DEFS,
                "tool_choice": "required",
                "max_tokens": 300,
                "temperature": 0.0,
            },
            timeout=15,
        )
        resp.raise_for_status()
        tool_calls = resp.json()["choices"][0]["message"].get("tool_calls", [])
        if not tool_calls:
            raise ValueError("LLM returned no tool calls")

        selected_tools, limits, focus_parts = [], {}, []
        for tc in tool_calls:
            name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])
            selected_tools.append(name)
            limits[name] = max(1, int(args.get("limit", 3)))
            if f := args.get("focus", "").strip():
                focus_parts.append(f)

        primary = selected_tools[0]
        focus = " ".join(focus_parts) + " " + _BREVITY
        reasoning = f"LLM selected: {', '.join(selected_tools)}"
        return selected_tools, reasoning, {"primary": primary, "limits": limits, "focus": focus}

    except Exception:
        return select_tools(question)


# ── Qdrant Search Helpers ─────────────────────────────────────────────────────

async def _search_reviews(client: QdrantClient, vec, asin: str, limit: int = 5):
    t0 = time.time()
    hits = await asyncio.to_thread(
        client.query_points,
        collection_name=QDRANT_COLLECTIONS["reviews"],
        query=vec,
        query_filter=Filter(must=[FieldCondition(key="asin", match=MatchValue(value=asin))]),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    ms = round((time.time() - t0) * 1000)
    points = hits.points
    score = round(sum(p.score for p in points) / len(points), 4) if points else 0.0
    return points, ms, score


async def _search_knowledge(client: QdrantClient, vec, limit: int = 3):
    t0 = time.time()
    hits = await asyncio.to_thread(
        client.query_points,
        collection_name=QDRANT_COLLECTIONS["knowledge"],
        query=vec,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    ms = round((time.time() - t0) * 1000)
    points = hits.points
    score = round(sum(p.score for p in points) / len(points), 4) if points else 0.0
    return points, ms, score


async def _search_visual(client: QdrantClient, vec, asin: str, limit: int = 1):
    t0 = time.time()
    hits = await asyncio.to_thread(
        client.query_points,
        collection_name=QDRANT_COLLECTIONS["visual_semantic"],
        query=vec,
        query_filter=Filter(must=[FieldCondition(key="asin", match=MatchValue(value=asin))]),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    ms = round((time.time() - t0) * 1000)
    points = hits.points
    score = round(sum(p.score for p in points) / len(points), 4) if points else 0.0
    return points, ms, score


# ── Retrieval Reflection ──────────────────────────────────────────────────────

def _reflect_retrieval(intent, top_reviews, top_knowledge, top_visual, product):
    """Returns (confidence, needs_knowledge_fallback, hints[])."""
    primary = intent["primary"]
    useful_knowledge = [p for p in top_knowledge if p.score > 0.3]
    review_count = len(top_reviews)
    hints = []
    needs_fallback = False

    if primary == "knowledge_search":
        if len(useful_knowledge) == 0:
            needs_fallback = True
            hints.append(
                "No expert knowledge found for this product — answer is based on customer reviews only. "
                "Confidence is lower than usual."
            )
            confidence = "low"
        elif len(useful_knowledge) == 1:
            hints.append("Limited expert knowledge available — supplementing with customer experience.")
            confidence = "medium"
        else:
            confidence = "high"
    elif primary == "review_search":
        if review_count == 0:
            hints.append("No customer reviews found for this product on this topic.")
            confidence = "low"
        elif review_count < 3:
            hints.append(
                f"Only {review_count} relevant review(s) found — "
                "the pattern may not be representative. Express appropriate uncertainty."
            )
            confidence = "medium"
        else:
            confidence = "high"
    else:  # visual_search primary
        if not top_visual:
            hints.append("No visual description found for this product.")
            confidence = "low"
        elif review_count == 0 and len(useful_knowledge) == 0:
            hints.append("Visual description available but no supporting reviews or knowledge.")
            confidence = "medium"
        else:
            confidence = "high"

    return confidence, needs_fallback, hints


async def _knowledge_fallback(client: QdrantClient, product: dict, original_question: str):
    """Re-query knowledge using product material+category when question phrasing doesn't match."""
    attrs = product.get("attributes", {})
    material = attrs.get("material", "")
    category = product.get("category", "")
    fallback_text = " ".join(filter(None, [material, category, original_question])).strip()
    if not fallback_text:
        return [], 0, 0.0
    fallback_vec = await asyncio.to_thread(embed, fallback_text)
    return await _search_knowledge(client, fallback_vec, limit=3)


# ── Conflict Detection (Qdrant-point version for legacy) ─────────────────────

def _detect_conflicts_points(top_knowledge, top_reviews) -> dict:
    """Conflict detection for Qdrant ScoredPoint lists (used by legacy pipeline)."""
    if not top_knowledge or not top_reviews:
        return {"has_conflict": False, "details": "Insufficient sources for conflict check"}

    knowledge_text = " ".join(
        p.payload.get("text", "").lower() for p in top_knowledge if p.score > 0.3
    )
    review_text = " ".join(
        p.payload.get("text", "").lower() for p in top_reviews if p.score > 0.3
    )

    if not knowledge_text or not review_text:
        return {"has_conflict": False, "details": "No high-confidence sources to compare"}

    conflicts = []
    for know_signals, rev_signals, topic in _CONFLICT_PAIRS:
        if any(s in knowledge_text for s in know_signals) and any(s in review_text for s in rev_signals):
            conflicts.append(topic)

    if conflicts:
        return {
            "has_conflict": True,
            "details": f"Conflict detected in: {', '.join(conflicts)}. Reviews contradict knowledge base claims.",
        }
    return {"has_conflict": False, "details": "Knowledge base and reviews are consistent"}


# ── Main Entry Point ──────────────────────────────────────────────────────────

async def run_legacy_query(req, client: QdrantClient) -> dict:
    """
    Execute the legacy single-pass pipeline and return a response dict.
    `req` must have: .asin, .question, .history, .user_context
    """
    start = time.time()

    question_vec = await asyncio.to_thread(embed, req.question)
    embed_ms = round((time.time() - start) * 1000)

    selected_tools, reasoning, intent = await select_tools_llm(req.question)
    limits = intent["limits"]

    tasks = {}
    if "review_search" in selected_tools:
        tasks["review_search"] = _search_reviews(client, question_vec, req.asin, limit=limits.get("review_search", 5))
    if "knowledge_search" in selected_tools:
        tasks["knowledge_search"] = _search_knowledge(client, question_vec, limit=limits.get("knowledge_search", 3))
    if "visual_search" in selected_tools:
        tasks["visual_search"] = _search_visual(client, question_vec, req.asin, limit=limits.get("visual_search", 1))

    search_results = dict(zip(tasks.keys(), await asyncio.gather(*tasks.values())))

    top_reviews, reviews_ms, reviews_score = search_results.get("review_search", ([], 0, 0.0))
    top_knowledge, knowledge_ms, knowledge_score = search_results.get("knowledge_search", ([], 0, 0.0))
    top_visual, visual_ms, visual_score = search_results.get("visual_search", ([], 0, 0.0))

    # Retrieval reflection
    product_data = {}  # product payload not available here; reflection uses it for material fallback
    confidence, needs_fallback, hints = _reflect_retrieval(intent, top_reviews, top_knowledge, top_visual, product_data)

    if needs_fallback:
        extra_knowledge, _, _ = await _knowledge_fallback(client, req._product, req.question)
        existing_ids = {p.id for p in top_knowledge}
        new_points = [p for p in extra_knowledge if p.id not in existing_ids]
        if new_points:
            top_knowledge = top_knowledge + new_points
            hints.append(
                f"Retrieved {len(new_points)} additional knowledge entry/entries "
                "using product material context as fallback query."
            )

    has_relevant_review = any(p.score > 0.3 for p in top_reviews)
    if not has_relevant_review and "knowledge_search" not in selected_tools:
        extra_knowledge, _, _ = await _search_knowledge(client, question_vec, limit=2)
        useful_extra = [p for p in extra_knowledge if p.score > 0.3]
        if useful_extra:
            top_knowledge = useful_extra
            hints.append(
                f"No relevant reviews found for this query — "
                f"supplemented with {len(useful_extra)} knowledge entry/entries."
            )

    # Context assembly
    product = getattr(req, "_product", {})
    attrs = product.get("attributes", {})
    _REVIEW_MAX = max(80, 450 // max(len(top_reviews), 1))
    sections = {}
    if top_reviews:
        lines = ["# Customer Reviews"]
        for p in top_reviews:
            stars = "★" * p.payload["rating"] + "☆" * (5 - p.payload["rating"])
            height = p.payload.get("reviewer_height", "")
            height_str = f" | {height}cm" if height else ""
            text = _first_sentence(p.payload["text"], _REVIEW_MAX)
            lines.append(f'- {stars}{height_str}: "{text}"')
        sections["reviews"] = "\n".join(lines)

    if top_knowledge:
        lines = ["# Expert Knowledge"]
        for p in top_knowledge:
            if p.score > 0.3:
                lines.append(p.payload["text"])
        if len(lines) > 1:
            sections["knowledge"] = "\n".join(lines)

    if top_visual:
        sections["visual"] = f"# Visual Description\n{top_visual[0].payload['text']}"

    section_order = _SECTION_ORDER.get(intent["primary"], ["reviews", "knowledge", "visual"])
    ordered_sections = [sections[k] for k in section_order if k in sections]

    evidence_section = f"# Evidence Quality\nConfidence: {confidence.upper()}"
    if hints:
        evidence_section += "\n" + "\n".join(f"- {h}" for h in hints)

    uc = req.user_context
    uc_lines = []
    if uc.height:
        uc_lines.append(f"Height: {uc.height}cm")
    if uc.weight:
        uc_lines.append(f"Weight: {uc.weight}kg")
    if uc.temp_target:
        uc_lines.append(f"Target temperature: {uc.temp_target}")
    if uc.skin_sensitive is not None:
        uc_lines.append(f"Skin sensitive: {'yes' if uc.skin_sensitive else 'no'}")
    user_context_section = ("# User Profile\n" + "\n".join(uc_lines)) if uc_lines else None

    context_parts = [
        "You are ShopSense, an accessible AI shopping assistant helping visually impaired users.\n",
        f"# Product\n"
        f"Name: {product.get('name', '')}\nBrand: {product.get('brand', '')}\nPrice: CHF {product.get('price', '')}\n"
        f"Material: {attrs.get('material', '')}\nColor: {attrs.get('color', '')}\n"
        f"Description: {product.get('description', '')}\n",
        evidence_section,
    ]
    if user_context_section:
        context_parts.append(user_context_section)
    context_parts += ordered_sections + [f"\n{intent['focus']}"]
    context = "\n\n".join(context_parts)

    # LLM call
    base_url = os.getenv("DASHSCOPE_BASE_URL", "https://api.groq.com/openai/v1")
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("HF_API_KEY")
    model = os.getenv("TEXT_MODEL", "llama-3.3-70b-versatile")

    answer = "[Error] LLM not configured."
    try:
        resp = await asyncio.to_thread(
            req_lib.post,
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": context},
                    *req.history[-6:],
                    {"role": "user", "content": req.question},
                ],
                "max_tokens": 160,
                "temperature": 0.5,
            },
            timeout=60,
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        answer = f"[LLM Error] {e}"

    total_ms = round((time.time() - start) * 1000)

    tool_results = []
    if "review_search" in selected_tools:
        tool_results.append({"tool_name": "review_search", "duration_ms": reviews_ms, "relevance_score": reviews_score})
    if "knowledge_search" in selected_tools:
        tool_results.append({"tool_name": "knowledge_search", "duration_ms": knowledge_ms, "relevance_score": knowledge_score})
    if "visual_search" in selected_tools:
        tool_results.append({"tool_name": "visual_search", "duration_ms": visual_ms, "relevance_score": visual_score})

    return {
        "answer": answer,
        "tool_selection": {"reasoning": reasoning, "tools": selected_tools},
        "tool_results": tool_results,
        "context_assembly": context,
        "reflection": {
            "confidence": confidence,
            "fallback_triggered": needs_fallback,
            "hints": hints,
        },
        "conflict_detection": _detect_conflicts_points(top_knowledge, top_reviews),
        "timing": {"embed_ms": embed_ms, "total_ms": total_ms},
    }
