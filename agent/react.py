"""
agent/react.py

ReAct agent loop for ShopSense v2.

Exports:
    react_loop()              — main loop called by /api/query
    _detect_conflicts()       — post-loop knowledge-vs-review conflict check
    _build_retrieval_summary()— compress trace to one-line history prefix
    _first_sentence()         — shared text utility
"""

import asyncio
import json
import re
import time

from core.llm import complete

from agent.tools.review_search import SemanticReviewSearchTool
from agent.tools.knowledge import KnowledgeRetrievalTool
from agent.tools.visual import VisualSemanticSearchTool
from agent.tools.base import ToolResult

# ── Tool singletons (shared across requests) ──────────────────────────────────
_TOOL_REVIEW = SemanticReviewSearchTool()
_TOOL_KNOWLEDGE = KnowledgeRetrievalTool()
_TOOL_VISUAL = VisualSemanticSearchTool()


# ── Text utility ──────────────────────────────────────────────────────────────

def _first_sentence(text: str, max_chars: int) -> str:
    """
    Return the first complete sentence of text, capped at max_chars.
    Falls back to word-boundary truncation if no sentence boundary found.
    """
    for punct in (". ", "! ", "? "):
        idx = text.find(punct)
        if 0 < idx < max_chars:
            return text[:idx + 1]
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


# ── Conflict Detection ────────────────────────────────────────────────────────

# A "claim" is a promise made about the product. It can come from the seller's own
# listing (title, description, attributes) or from the expert material knowledge
# base. Each tuple is (claim_signals, review_signals, topic).
_CONFLICT_PAIRS = [
    (
        {"hypoallergenic", "suitable for sensitive", "safe for sensitive",
         "gentle on skin", "non-irritating", "ultra-soft", "soft to touch",
         "soft to the touch"},
        {"itchy", "irritat", "allergic", "rash", "scratch"},
        "skin sensitivity",
    ),
    (
        {"true to size", "runs true", "standard sizing", "regular fit"},
        {"size up", "runs small", "too small", "size down", "runs large", "too big", "too large"},
        "sizing",
    ),
    (
        {"relaxed fit", "oversized", "roomy", "generous fit"},
        {"size up", "runs small", "too small", "too tight"},
        "sizing",
    ),
    (
        {"retains warmth", "keeps you warm", "warm down to", "suitable for -",
         "rated for 0°c", "rated for -", "extremely warm", "exceptionally warm",
         "very warm", "warm for its weight", "for extreme cold", "arctic", "thermal"},
        {"runs cold", "not warm enough", "not warm", "no warmth", "colder than expected"},
        "warmth",
    ),
    (
        {"waterproof", "fully waterproof", "repels water", "dwr", "beads water"},
        {"soaked", "soaks through", "not waterproof", "leaks", "wet through",
         "let water in"},
        "water resistance",
    ),
    (
        {"durable", "long-lasting", "hard-wearing", "reinforced", "abrasion"},
        {"falls apart", "poor quality", "pilling badly", "worn out quickly",
         "came apart", "came loose", "feel cheap", "feels cheap"},
        "durability",
    ),
]

_CLAIM_SPLIT = re.compile(r"(?<=[.!?])\s+|;\s*")


def _snippet(segment: str, needle: str, width: int = 80) -> str:
    """Short window of `segment` around `needle`, used to quote the evidence."""
    low = segment.lower()
    idx = low.find(needle) if len(low) == len(segment) else -1
    if idx < 0:
        return _first_sentence(segment.strip(), width)
    start = max(0, idx - width // 3)
    end = min(len(segment), idx + len(needle) + width)
    out = segment[start:end].strip()
    if start > 0:
        out = "…" + out
    if end < len(segment):
        out = out + "…"
    return out


# Word-boundary matching matters: a plain "no " substring also hits "meriNO wool",
# which would silently cancel every complaint about a merino garment.
_NEGATION_RE = re.compile(
    r"n't|\bnon-|\b(?:not|no|never|without|nothing|zero|hardly|barely|less)\b"
)

# Phrases where a signal word is part of a longer term that means something else.
# "Durable Water Repellent" is a coating name, not a promise that the item lasts.
_MATCH_EXCLUSIONS = ("durable water repellent",)


def _in_excluded_phrase(low: str, idx: int, length: int) -> bool:
    """True when the match at `idx` sits inside one of `_MATCH_EXCLUSIONS`."""
    for phrase in _MATCH_EXCLUSIONS:
        pos = 0
        while True:
            found = low.find(phrase, pos)
            if found < 0:
                break
            if found <= idx and idx + length <= found + len(phrase):
                return True
            pos = found + 1
    return False


def _is_negated(low: str, idx: int, window: int = 40) -> bool:
    """
    True when the match at `idx` is cancelled by a negation just before it.

    "the collar doesn't irritate my neck" and "non-irritating" both contain the
    complaint token "irritat" while saying the opposite. Only the current
    sentence is inspected, so a negation two sentences back cannot silently
    swallow a real complaint.
    """
    before = low[:idx]
    cut = max(before.rfind("."), before.rfind("!"), before.rfind("?"))
    if cut >= 0:
        before = before[cut + 1:]
    before = before[-window:]
    # the slice can start mid-word; drop that fragment so it cannot fake a cue
    before = re.sub(r"^\S*", "", before)
    return bool(_NEGATION_RE.search(before))


def _find_signal(segments: list, signals: set):
    """
    First (segment, signal) pair where a signal occurs and is not negated.

    Signals that carry their own negation ("not warm enough") are matched as-is.
    Signals are sorted so the quoted evidence is stable across runs.
    """
    for segment in segments:
        low = segment.lower()
        for signal in sorted(signals):
            carries_negation = bool(_NEGATION_RE.search(signal))
            start = 0
            while True:
                idx = low.find(signal, start)
                if idx < 0:
                    break
                if (
                    not _in_excluded_phrase(low, idx, len(signal))
                    and (carries_negation or not _is_negated(low, idx))
                ):
                    return segment, signal
                start = idx + len(signal)
    return None, None


def _official_claims(product: dict) -> list:
    """
    The seller's own promises: title, description sentences and attribute values.

    These are the claims the listing is accountable for. The knowledge base is
    generic background about a material, not something the seller said, so the
    two are kept apart and reported under different source labels.
    """
    if not product:
        return []
    segments = []
    name = (product.get("name") or "").strip()
    if name:
        segments.append(name)
    description = (product.get("description") or "").strip()
    if description:
        segments.extend(s.strip() for s in _CLAIM_SPLIT.split(description) if s.strip())
    attributes = product.get("attributes") or {}
    if isinstance(attributes, dict):
        for key, value in attributes.items():
            if isinstance(value, str) and value.strip():
                segments.append(f"{key}: {value.strip()}")
    return segments


def _detect_conflicts(top_knowledge: list, top_reviews: list, product: dict = None) -> dict:
    """
    Flag topics where a claim about the product is contradicted by buyers.

    Two claim sources are checked, in order of precedence:
      1. the official listing   — the seller's own title, description, attributes
      2. the knowledge base     — generic expert entries retrieved for this query

    Source 1 is what the product promise is about, and it is always available,
    so a conflict is surfaced even when no knowledge entry was retrieved.

    Returns {"has_conflict", "details", "conflicts": [{topic, source, claim, counter}]}.
    """
    reviews = [
        item.get("text", "")
        for item in (top_reviews or [])
        if item.get("text") and item.get("relevance_score", 0) > 0.3
    ]
    if not reviews:
        return {
            "has_conflict": False,
            "details": "No high-confidence reviews to compare against",
            "conflicts": [],
        }

    knowledge = [
        item.get("text", "")
        for item in (top_knowledge or [])
        if item.get("text") and item.get("relevance_score", 0) > 0.3
    ]
    claim_sources = [
        ("the official listing", _official_claims(product)),
        ("the material knowledge base", knowledge),
    ]

    conflicts = []
    seen_topics = set()
    for claim_signals, review_signals, topic in _CONFLICT_PAIRS:
        if topic in seen_topics:
            continue
        review_segment, review_signal = _find_signal(reviews, review_signals)
        if review_segment is None:
            continue
        for source, segments in claim_sources:
            claim_segment, claim_signal = _find_signal(segments, claim_signals)
            if claim_segment is None:
                continue
            seen_topics.add(topic)
            conflicts.append({
                "topic": topic,
                "source": source,
                "claim": _snippet(claim_segment, claim_signal),
                "counter": _snippet(review_segment, review_signal),
            })
            break

    if not conflicts:
        return {
            "has_conflict": False,
            "details": "Claims and reviews are consistent",
            "conflicts": [],
        }

    details = "; ".join(
        f'on {c["topic"]}, {c["source"]} says "{c["claim"]}" '
        f'but a buyer reports "{c["counter"]}"'
        for c in conflicts
    )
    return {"has_conflict": True, "details": details, "conflicts": conflicts}


def _build_retrieval_summary(trace: list) -> str:
    """
    Compress a ReAct trace into a one-line retrieval summary for API response.
    e.g. "review×5·82%, knowledge×3·71%"
    """
    parts = []
    for step in trace:
        if not step.get("actions"):
            continue
        for action, obs in zip(step["actions"], step.get("observations", [])):
            short = action["tool"].replace("_search", "")
            pct = round(obs["score"] * 100)
            parts.append(f"{short}×{obs['results']}·{pct}%")
    return ", ".join(parts) if parts else "no retrieval"


_ALL_TOOLS = {"review_search", "knowledge_search", "visual_search"}

_TOOL_LABELS = {
    "review_search":    "customer reviews",
    "knowledge_search": "material/technical knowledge",
    "visual_search":    "visual appearance",
}


def _build_context_summary(trace: list) -> str:
    """
    Build a directive context summary for LLM re-injection.
    Shows what's already been retrieved and which tools haven't been used,
    so the LLM can decide whether to search more or answer now.
    e.g. "Already retrieved: reviews (5 results, 82% conf), knowledge (3 results, 71% conf).
          Not yet searched: visual appearance. Answer now if sufficient, or search what's missing."
    """
    used: dict[str, dict] = {}
    for step in trace:
        if not step.get("actions"):
            continue
        for action, obs in zip(step["actions"], step.get("observations", [])):
            name = action["tool"]
            if name not in used:
                used[name] = {"results": 0, "scores": []}
            used[name]["results"] += obs["results"]
            used[name]["scores"].append(obs["score"])

    if not used:
        return ""

    covered = []
    for name, data in used.items():
        avg_conf = round(sum(data["scores"]) / len(data["scores"]) * 100)
        label = _TOOL_LABELS.get(name, name.replace("_search", ""))
        covered.append(f"{label} ({data['results']} results, {avg_conf}% conf)")

    unused_labels = [
        _TOOL_LABELS[t] for t in sorted(_ALL_TOOLS - set(used.keys()))
    ]

    parts = [f"Already retrieved: {', '.join(covered)}."]
    if unused_labels:
        parts.append(f"Not yet searched: {', '.join(unused_labels)}.")
    parts.append("Answer now if you have enough, or use a different tool to fill the gap.")

    return " ".join(parts)


# ── Retrieval Reflection ──────────────────────────────────────────────────────

async def _reflect(
    question: str,
    retrieved: dict,
    trace: list,
) -> dict:
    """
    Lightweight LLM-based reflection: evaluate whether retrieved data is
    sufficient to answer the question before the next iteration.
    Returns {"sufficient": bool, "confidence": "high|medium|low",
             "gaps": str, "next_action": "answer|search_more"}
    """
    n_reviews = len(retrieved.get("reviews", []))
    n_knowledge = len(retrieved.get("knowledge", []))
    n_visual = len(retrieved.get("visual", []))

    # Extract avg relevance scores per tool from trace observations
    scores: dict[str, list[float]] = {}
    for step in trace:
        for action, obs in zip(step.get("actions", []), step.get("observations", [])):
            t = action["tool"]
            scores.setdefault(t, []).append(obs["score"])
    avg = {t: sum(v) / len(v) for t, v in scores.items()}

    def _fmt(n: int, tool: str) -> str:
        if n == 0:
            return "0"
        sc = avg.get(tool)
        return f"{n} (avg relevance {sc:.0%})" if sc is not None else str(n)

    prompt = (
        f'Question: "{question}"\n\n'
        f"Data retrieved so far:\n"
        f"- Customer reviews: {_fmt(n_reviews, 'review_search')}\n"
        f"- Material/technical knowledge: {_fmt(n_knowledge, 'knowledge_search')}\n"
        f"- Visual descriptions: {_fmt(n_visual, 'visual_search')} "
        f"(optional — only needed for color/style/appearance questions)\n\n"
        "Is this sufficient to answer the question confidently? "
        "Visual descriptions being absent is NOT a gap unless the question is about appearance.\n"
        'Reply ONLY with valid JSON: {"sufficient": true/false, '
        '"confidence": "high"/"medium"/"low", '
        '"gaps": "specific missing info, or null if none", '
        '"next_action": "answer"/"search_more"}'
    )

    try:
        message = await asyncio.to_thread(complete, {
            "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a retrieval quality evaluator for a shopping assistant. "
                            "Assess whether the retrieved data is sufficient to answer the question. "
                            "Reply ONLY with valid JSON, no other text."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
        })
        raw = message["content"].strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(m.group() if m else raw)
        return {
            "sufficient": bool(result.get("sufficient", True)),
            "confidence": result.get("confidence", "medium"),
            "gaps": result.get("gaps") or "none",
            "next_action": result.get("next_action", "answer"),
        }
    except Exception as e:
        return {"sufficient": True, "confidence": "medium", "gaps": "none", "next_action": "answer", "error": str(e)}


# ── ReAct Tool Definitions ────────────────────────────────────────────────────

_REACT_TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "review_search",
            "description": (
                "Search customer reviews for this product. "
                "Use for: sizing/fit, durability, real-world experience, value, skin reactions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "What to look for, phrased the way a reviewer would write it, "
                            "e.g. 'runs small, had to size up' or 'still warm at minus ten'. "
                            "Sharpen or rephrase it when an earlier search came back off-topic."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of reviews to retrieve (1–8). Use more to aggregate opinions.",
                        "minimum": 1,
                        "maximum": 8,
                    },
                },
                "required": ["query", "limit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_search",
            "description": (
                "Search expert fabric/material knowledge base. "
                "Use for: temperature ratings, material properties (hypoallergenic, waterproof, breathability), "
                "care instructions, technical specs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "What to look up, phrased the way a fabric reference would put it, "
                            "e.g. 'down fill power temperature rating' or 'merino fibre diameter "
                            "skin irritation'. Name the material when you know it."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of knowledge entries to retrieve (1–5).",
                        "minimum": 1,
                        "maximum": 5,
                    },
                },
                "required": ["query", "limit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "visual_search",
            "description": (
                "Search visual/image descriptions of the product. "
                "Use for: color, appearance, silhouette, texture, design details."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Which visual aspect you need, e.g. 'colour and shade', 'collar and "
                            "buttons', 'overall silhouette and length'."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of visual descriptions to retrieve (1–2).",
                        "minimum": 1,
                        "maximum": 2,
                    },
                },
                "required": ["query", "limit"],
            },
        },
    },
]


# ── System Prompt Builder ─────────────────────────────────────────────────────

# Shared by the ReAct agent and the browser-extension endpoint so the two
# never drift into speaking differently to the same user.
VOICE_RULES = (
    "## Output Format — READ THIS CAREFULLY\n"
    "Your answer will be read aloud by a screen reader. Sentence order is critical.\n\n"
    "REQUIRED sentence order:\n"
    "  Sentence 1 — Verdict: a direct yes/no/likely/unclear answer to the question. "
    "This is the FIRST thing the user hears. Never bury it.\n"
    "  Sentence 2 — Evidence: cite the source naturally "
    "(e.g. 'Most reviewers say...', 'The product specs confirm...', "
    "'Reviews are mixed, with some saying... and others saying...').\n"
    "  Sentence 3 — Tip (optional): one concrete, actionable tip if useful.\n\n"
    "HARD RULES:\n"
    "- Total length: 2 to 3 sentences. Never more.\n"
    "- Plain prose only. No bullet points, no numbered lists, no headers.\n"
    "- No symbols that sound wrong when read aloud: no %, no /, no arrows, "
    "no star characters, no currency symbols — spell them out instead.\n"
    "- Do not start with 'I', 'Based on', 'As an AI', or 'According to my search'.\n"
    "- If data is missing, start with: 'I could not find enough information about [topic] "
    "for this product.' Then stop — do not speculate.\n\n"
)


def _build_react_system(product: dict, user_context) -> str:
    attrs = product.get("attributes", {})
    product_section = (
        f"Name: {product['name']}\n"
        f"Brand: {product['brand']}\n"
        f"Price: CHF {product['price']}\n"
        f"Material: {attrs.get('material', 'not specified')}\n"
        f"Color: {attrs.get('color', 'not specified')}\n"
        f"Description: {product.get('description', '')}"
    )

    uc_lines = []
    if user_context.height:
        uc_lines.append(f"Height: {user_context.height} centimetres")
    if user_context.weight:
        uc_lines.append(f"Weight: {user_context.weight} kilograms")
    if user_context.temp_target:
        uc_lines.append(f"Target temperature: {user_context.temp_target}")
    if user_context.skin_sensitive is not None:
        uc_lines.append(f"Skin sensitive: {'yes' if user_context.skin_sensitive else 'no'}")
    user_section = "\n".join(uc_lines) if uc_lines else "None provided."

    personal_hint = ""
    if user_context.height and user_context.weight:
        personal_hint = (
            f"The user is {user_context.height} cm tall and weighs {user_context.weight} kg. "
            "When sizing or fit comes up, apply these numbers directly in your answer."
        )
    elif user_context.height:
        personal_hint = (
            f"The user is {user_context.height} cm tall. "
            "Apply this when discussing sizing or fit."
        )

    return (
        "You are ShopSense, a voice-first shopping assistant built for visually impaired users.\n"
        "You answer questions ONLY about the product listed below.\n"
        "You NEVER answer general questions unrelated to this product.\n"
        "You NEVER add knowledge that was not returned by a search tool.\n\n"

        f"## Product\n{product_section}\n\n"
        f"## User Profile\n{user_section}\n"
        f"{personal_hint}\n\n"

        "## Retrieval Rules\n"
        "- You MUST call at least one search tool before writing any answer.\n"
        "- Every tool takes a `query`. Write it in the words the source itself would use, "
        "not the user's phrasing: a reviewer writes 'runs small', a fabric reference writes "
        "'fill power temperature rating'.\n"
        "- After each search result, decide: can I answer confidently now? "
        "If yes, write your answer. If not, search again — either a different tool, or the "
        "same tool with a sharper query aimed at what was missing.\n"
        "- When a [Context Update] names a specific gap, your next query must target that gap.\n"
        "- Maximum 3 searches total. After the third, answer with whatever you have.\n"
        "- If results are irrelevant or empty, say so explicitly — do not fill the gap with guesses.\n\n"

        + VOICE_RULES +

        "## Conflict Handling\n"
        "If a [Context Update] message reports a conflict, do NOT give a simple yes/no verdict.\n"
        "Use this format instead:\n"
        "  Sentence 1 — Conflict verdict: state both sides directly and name each source, "
        "e.g. 'The listing says X, but several buyers report Y.' The update tells you whether "
        "the claim came from the official listing or from the material knowledge base — "
        "do not swap the two, the listing is what the seller promised.\n"
        "  Sentence 2 — Trust guidance: explain which source is more reliable for this specific claim "
        "and why (specs are authoritative for technical ratings; reviews are authoritative for real-world fit, "
        "durability, and skin reactions).\n"
        "  Sentence 3 — Practical tip: give a concrete recommendation that accounts for the conflict.\n"
        "NEVER pick one side and ignore the other when a conflict has been flagged."
    )


# ── Tool Observation Formatter ────────────────────────────────────────────────

def _format_tool_observation(name: str, result: ToolResult, is_primary: bool = True) -> str:
    """
    Format a ToolResult as an LLM-readable observation string.

    is_primary: True  → primary source, larger char budget, more detail
                False → secondary source, compressed budget
    """
    if not result.success or not result.data:
        return "No results found."

    if name == "review_search":
        reviews = result.data.get("reviews", [])
        if not reviews:
            return "No results found."
        per_item = 220 if is_primary else 100
        lines = []
        for r in reviews:
            rating = r.get("rating", 3)
            text = _first_sentence(r.get("text", ""), per_item)
            height = r.get("reviewer_height", "")
            h = f", {height}cm" if height else ""
            lines.append(f"- [{rating}/5{h}] \"{text}\"")
        return "\n".join(lines)

    if name == "knowledge_search":
        items = result.data.get("knowledge_items", [])
        score_floor = 0.15 if is_primary else 0.35
        relevant = [k for k in items if k.get("relevance_score", 0) > score_floor]
        if not relevant:
            return "No relevant knowledge found (low confidence scores)."
        if is_primary:
            return "\n\n".join(k.get("text", "") for k in relevant)
        return "\n\n".join(k.get("text", "")[:300] for k in relevant)

    if name == "visual_search":
        items = result.data.get("visual_items", [])
        if not items:
            return "No visual description found."
        pool = items if is_primary else items[:1]
        return "\n\n".join(v.get("description", "") for v in pool) or "No visual description found."

    return str(result.data)


# ── ReAct Loop ────────────────────────────────────────────────────────────────

async def react_loop(
    question: str,
    asin: str,
    product: dict,
    history: list,
    user_context,
    max_iter: int = 3,
) -> tuple[str, list, dict]:
    """
    ReAct loop: Think → Act (search) → Observe → repeat until confident or max_iter.
    Returns (answer, trace, retrieved_data).
    """
    messages = [
        {"role": "system", "content": _build_react_system(product, user_context)},
        *history,
        {"role": "user", "content": question},
    ]

    trace: list[dict] = []
    retrieved: dict[str, list] = {"reviews": [], "knowledge": [], "visual": []}
    answer = "[No answer generated]"
    last_conflict: dict = {"has_conflict": False, "details": "", "conflicts": []}

    for iteration in range(max_iter):
        tool_choice = "required" if iteration == 0 else "auto"

        try:
            response_message = await asyncio.to_thread(complete, {
                "messages": messages,
                "tools": _REACT_TOOL_DEFS,
                "tool_choice": tool_choice,
            })
        except Exception as e:
            answer = f"[LLM Error] {e}"
            break

        tool_calls = response_message.get("tool_calls", [])

        if not tool_calls:
            answer = (response_message.get("content") or "").strip()
            trace.append({"iteration": iteration + 1, "action": "final_answer"})
            break

        # Execute all tool calls in this iteration in parallel
        async def _exec(tc):
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except (TypeError, ValueError):
                args = {}
            limit = max(1, int(args.get("limit", 3) or 3))
            # The agent rewrites the query to target whatever the reflection said
            # was missing; fall back to the user's own words when it supplies none.
            search_query = str(args.get("query") or "").strip() or question
            t0 = time.time()
            if name == "review_search":
                result = await _TOOL_REVIEW.execute(query=search_query, asin=asin, top_k=limit)
                retrieved["reviews"].extend(result.data.get("reviews", []) if result.success else [])
            elif name == "knowledge_search":
                result = await _TOOL_KNOWLEDGE.execute(query=search_query, top_k=limit)
                retrieved["knowledge"].extend(result.data.get("knowledge_items", []) if result.success else [])
            elif name == "visual_search":
                result = await _TOOL_VISUAL.execute(asin=asin, query=search_query, top_k=limit)
                retrieved["visual"].extend(result.data.get("visual_items", []) if result.success else [])
            else:
                result = ToolResult(tool_name=name, success=False, data=None, relevance_score=0.0)
            ms = round((time.time() - t0) * 1000)
            return tc["id"], name, search_query, limit, result, ms

        exec_results = await asyncio.gather(*[_exec(tc) for tc in tool_calls])

        messages.append({
            "role": "assistant",
            "content": response_message.get("content"),
            "tool_calls": tool_calls,
        })

        primary_tool_id = tool_calls[0]["id"] if tool_calls else None
        iter_actions, iter_observations = [], []
        for tool_id, name, search_query, limit_used, result, ms in exec_results:
            obs_text = _format_tool_observation(name, result, is_primary=(tool_id == primary_tool_id))
            messages.append({"role": "tool", "tool_call_id": tool_id, "content": obs_text})
            n_results = (
                len(result.data.get("reviews") or result.data.get("knowledge_items") or result.data.get("visual_items") or [])
                if result.success and result.data else 0
            )
            iter_actions.append({"tool": name, "limit": limit_used, "query": search_query})
            iter_observations.append({
                "tool": name,
                "results": n_results,
                "score": round(result.relevance_score, 3),
                "duration_ms": ms,
            })

        trace.append({"iteration": iteration + 1, "actions": iter_actions, "observations": iter_observations})

        # Conflict check runs on every round, not only on the ones that inject
        # context, so the forced-final path below can mention it too. The panel
        # must never report a conflict the answer never heard about.
        last_conflict = _detect_conflicts(retrieved["knowledge"], retrieved["reviews"], product)
        trace[-1]["conflict"] = last_conflict

        # ── Retrieval Reflection + Context Engineering ──
        # After each round (except the last) an LLM evaluates whether the data
        # retrieved so far is sufficient, then we re-inject a directive that
        # steers the next step: answer now, or fill a specific gap.
        if iteration < max_iter - 1:
            reflection = await _reflect(
                question=question,
                retrieved=retrieved,
                trace=trace,
            )
            trace[-1]["reflection"] = reflection

            context_notes = []

            summary = _build_context_summary(trace)
            if summary:
                context_notes.append(summary)

            if last_conflict["has_conflict"]:
                context_notes.append(
                    f"Conflict detected — {last_conflict['details']}. "
                    "Acknowledge this conflict explicitly in your answer and name the "
                    "source on each side."
                )

            # Reflection drives the next move: search more vs. answer now.
            if reflection.get("next_action") == "search_more" and not reflection.get("sufficient"):
                gap = reflection.get("gaps", "none")
                context_notes.append(
                    f"Retrieval is incomplete (confidence: {reflection.get('confidence', 'low')}). "
                    f"Missing: {gap}. Search again with a query aimed squarely at that gap — "
                    "a different tool, or the same tool with sharper wording."
                )
            else:
                context_notes.append(
                    f"Retrieved data is sufficient (confidence: {reflection.get('confidence', 'medium')}). "
                    "Provide your final answer now without searching again."
                )

            if context_notes:
                injection = " ".join(context_notes)
                messages.append({"role": "user", "content": "[Context Update] " + injection})
                trace[-1]["context_injection"] = injection

    else:
        # Max iterations reached — force a final answer
        final_prompt = "You have gathered enough information. Provide your final answer now."
        if last_conflict["has_conflict"]:
            final_prompt += (
                f" A conflict was detected — {last_conflict['details']}. "
                "Use the conflict format: state both sides, name each source, then give a practical tip."
            )
        messages.append({"role": "user", "content": final_prompt})
        try:
            message = await asyncio.to_thread(complete, {"messages": messages})
            answer = (message.get("content") or "").strip()
            trace.append({"iteration": max_iter + 1, "action": "forced_final_answer"})
        except Exception as e:
            answer = f"[LLM Error] {e}"

    return answer, trace, retrieved
