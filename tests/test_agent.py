"""
tests/test_agent.py

Covers the two agent behaviours that are easiest to break without noticing:

  * conflict detection — which claims count as a promise, and when a negation
    ("doesn't irritate", "non-irritating") cancels an apparent complaint;
  * the ReAct loop — that a query the agent rewrote actually reaches the tool
    and is recorded in the trace, rather than the raw user question.

The Qdrant-backed tool classes are stubbed, so this needs no database, no API
key and no network. Run it directly:

    python tests/test_agent.py

or under pytest.
"""

import asyncio
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Stub the Qdrant-backed tools before agent.react imports them ─────────────

TOOL_CALLS = []


class _FakeToolResult:
    def __init__(self, data, score=0.7):
        self.tool_name = "fake"
        self.success = True
        self.data = data
        self.relevance_score = score


def _make_tool(label, payload_key, rows):
    class _Tool:
        async def execute(self, **kwargs):
            TOOL_CALLS.append({
                "tool": label,
                "query": kwargs.get("query"),
                "top_k": kwargs.get("top_k"),
            })
            return _FakeToolResult({payload_key: list(rows)})
    return _Tool


_REVIEW_ROWS = [{"text": "Runs small, I had to size up.", "relevance_score": 0.62, "rating": 3}]
_KNOWLEDGE_ROWS = [{"text": "Extra-fine merino is non-irritating.", "relevance_score": 0.55}]
_VISUAL_ROWS = [{"description": "An ivory ribbed turtleneck.", "relevance_score": 0.5}]

for _mod, _cls, _key, _label, _rows in [
    ("agent.tools.review_search", "SemanticReviewSearchTool", "reviews", "review_search", _REVIEW_ROWS),
    ("agent.tools.knowledge", "KnowledgeRetrievalTool", "knowledge_items", "knowledge_search", _KNOWLEDGE_ROWS),
    ("agent.tools.visual", "VisualSemanticSearchTool", "visual_items", "visual_search", _VISUAL_ROWS),
]:
    _stub = types.ModuleType(_mod)
    setattr(_stub, _cls, _make_tool(_label, _key, _rows))
    sys.modules[_mod] = _stub

import agent.react as R  # noqa: E402


# ── Fixtures ─────────────────────────────────────────────────────────────────

PRODUCT = {
    "name": "Merino Wool Turtleneck",
    "brand": "WoolCraft",
    "price": 89.99,
    "description": "100% extra-fine merino wool, relaxed fit. Safe for sensitive skin.",
    "attributes": {"material": "100% merino wool", "color": "ivory white"},
}


class _UserContext:
    height = 175
    weight = 65
    temp_target = None
    skin_sensitive = None


def _reviews(*texts, score=0.5):
    return [{"text": t, "relevance_score": score} for t in texts]


def _knowledge(*texts, score=0.5):
    return [{"text": t, "relevance_score": score} for t in texts]


# ── Conflict detection ───────────────────────────────────────────────────────

def test_official_listing_claim_conflicts_with_review():
    """The seller's own copy is a claim source, even with no knowledge entries."""
    result = R._detect_conflicts([], _reviews("Runs slim. Size up one."), PRODUCT)
    assert result["has_conflict"]
    assert result["conflicts"][0]["topic"] == "sizing"
    assert result["conflicts"][0]["source"] == "the official listing"


def test_knowledge_base_claim_conflicts_with_review():
    result = R._detect_conflicts(
        _knowledge("800 fill down keeps the wearer warm in arctic conditions."),
        _reviews("Not warm enough below -15."),
        None,
    )
    assert result["has_conflict"]
    assert result["conflicts"][0]["source"] == "the material knowledge base"


def test_no_claim_means_no_conflict():
    """A complaint alone is not a conflict — nobody promised otherwise."""
    silent = {"name": "Plain Tee", "description": "Cotton jersey, crew neck.", "attributes": {}}
    assert not R._detect_conflicts([], _reviews("Runs small, size up."), silent)["has_conflict"]


def test_negated_complaint_is_not_a_conflict():
    reviews = _reviews("The merino collar doesn't irritate my neck at all.")
    assert not R._detect_conflicts([], reviews, PRODUCT)["has_conflict"]


def test_praise_phrased_as_non_irritating_is_not_a_conflict():
    product = {"name": "Lounge Set", "description": "Ultra-soft to touch.", "attributes": {}}
    reviews = _reviews("Great for eczema. Non-irritating and breathable.")
    assert not R._detect_conflicts([], reviews, product)["has_conflict"]


def test_negation_in_an_earlier_sentence_does_not_mask_a_complaint():
    product = {"name": "Tee", "description": "Relaxed fit.", "attributes": {}}
    reviews = _reviews("I did not expect much. Runs small, had to size up.")
    assert R._detect_conflicts([], reviews, product)["has_conflict"]


def test_merino_is_not_read_as_a_negation():
    """A bare 'no ' substring also matches 'meriNO wool'; boundaries must be checked."""
    product = {
        "name": "Merino Crew",
        "description": "Soft merino wool, relaxed fit.",
        "attributes": {},
    }
    assert R._detect_conflicts([], _reviews("Runs small, size up."), product)["has_conflict"]


def test_dwr_coating_is_not_a_durability_claim():
    product = {
        "name": "Shell",
        "description": "Durable Water Repellent coating on the outer shell.",
        "attributes": {},
    }
    reviews = _reviews("One button came loose after two weeks.")
    assert not R._detect_conflicts([], reviews, product)["has_conflict"]


def test_water_resistant_is_not_contradicted_by_not_waterproof():
    """'Water resistant' is a weaker promise; a buyer saying so agrees with it."""
    product = {
        "name": "Softshell",
        "description": "Windproof and water-resistant.",
        "attributes": {},
    }
    reviews = _reviews("Water resistant, not waterproof. Soaks through in heavy rain.")
    assert not R._detect_conflicts([], reviews, product)["has_conflict"]


def test_low_relevance_sources_are_ignored():
    reviews = _reviews("Not warm enough at all.", score=0.1)
    product = {"name": "Coat", "description": "Extremely warm.", "attributes": {}}
    assert not R._detect_conflicts([], reviews, product)["has_conflict"]


def test_conflict_output_is_deterministic():
    reviews = _reviews("Runs slim. Size up one.")
    seen = {R._detect_conflicts([], reviews, PRODUCT)["details"] for _ in range(5)}
    assert len(seen) == 1


# ── ReAct loop ───────────────────────────────────────────────────────────────

def _run_loop(tool_arguments, question):
    """Drive react_loop with a scripted LLM: one tool round, then an answer."""
    TOOL_CALLS.clear()
    script = [
        {"tool_calls": [{"id": "c1", "function": {
            "name": "review_search", "arguments": tool_arguments}}]},
        {"content": "Likely runs small. Several buyers sized up."},
    ]
    state = {"n": 0}

    def _complete(body, config=None):
        messages = json.dumps(body["messages"])
        if "retrieval quality evaluator" in messages:
            return {"content": json.dumps({
                "sufficient": False, "confidence": "low",
                "gaps": "fit for a 175cm buyer", "next_action": "search_more",
            })}
        message = script[min(state["n"], len(script) - 1)]
        state["n"] += 1
        return message

    original = R.complete
    R.complete = _complete
    try:
        return asyncio.run(R.react_loop(
            question=question, asin="P003", product=PRODUCT,
            history=[], user_context=_UserContext(),
        ))
    finally:
        R.complete = original


def test_rewritten_query_reaches_the_tool_and_the_trace():
    _, trace, _ = _run_loop(
        json.dumps({"query": "runs small had to size up", "limit": 5}),
        "Will this fit me?",
    )
    assert TOOL_CALLS[0]["query"] == "runs small had to size up"
    assert TOOL_CALLS[0]["top_k"] == 5
    action = trace[0]["actions"][0]
    assert action["query"] == "runs small had to size up"
    assert action["limit"] == 5


def test_missing_query_falls_back_to_the_users_words():
    _run_loop(json.dumps({"limit": 3}), "Is the wool itchy?")
    assert TOOL_CALLS[0]["query"] == "Is the wool itchy?"


def test_malformed_tool_arguments_do_not_crash_the_request():
    answer, _, _ = _run_loop("{not valid json", "Does it shrink?")
    assert TOOL_CALLS[0]["query"] == "Does it shrink?"
    assert not answer.startswith("[LLM Error]")


def test_conflict_is_injected_back_into_the_agent_context():
    """The panel must never report a conflict the answer never heard about."""
    _, trace, _ = _run_loop(
        json.dumps({"query": "sizing", "limit": 5}), "Will this fit me?")
    assert trace[0]["conflict"]["has_conflict"]
    assert "Conflict detected" in trace[0]["context_injection"]


# ── Live product page (browser extension) ────────────────────────────────────

import agent.page as P  # noqa: E402
from config.settings import LLMConfig  # noqa: E402


def _payload(**overrides):
    fields = dict(asin="B01", title="", brand="", price="", description="",
                  bullets=[], reviews=[], image_url=None, question="")
    fields.update(overrides)
    return types.SimpleNamespace(**fields)


def _with_llm(api_key, call):
    """Run `call` with the page module seeing an LLM config with this key."""
    original = P.LLM
    P.LLM = LLMConfig(base_url="http://llm.invalid/v1", api_key=api_key, model="test", extra_body={})
    try:
        return call()
    finally:
        P.LLM = original


def _without_a_model(call):
    """Run `call` with no API key configured, so the offline path is exercised."""
    return _with_llm(None, call)


def test_page_answer_flags_the_listing_against_the_pages_own_reviews():
    payload = _payload(
        title="Oversized Corduroy Overshirt",
        description="Oversized shirt-jacket silhouette, 100% cotton corduroy.",
        reviews=["Runs small, I had to size up.", "Lovely colour."],
    )
    result = _without_a_model(lambda: asyncio.run(P.answer_from_page(payload)))
    assert result["conflict_detection"]["has_conflict"]
    assert result["reviews_read"] == 2
    assert "size up" in result["answer"] or "Runs small" in result["answer"]


def test_page_answer_survives_with_no_model_configured():
    payload = _payload(title="Plain Tee", description="Cotton jersey.",
                       reviews=["Nice shirt."])
    result = _without_a_model(lambda: asyncio.run(P.answer_from_page(payload)))
    assert result["source"] == "page_only"
    assert result["answer"]


def test_page_answer_says_so_when_no_reviews_were_visible():
    payload = _payload(title="Plain Tee", description="Cotton jersey.")
    result = _without_a_model(lambda: asyncio.run(P.answer_from_page(payload)))
    assert not result["conflict_detection"]["has_conflict"]
    assert "No reviews" in result["answer"]


def test_page_answer_uses_the_model_when_one_is_reachable():
    payload = _payload(title="Tee", description="Relaxed fit.",
                       reviews=["Runs small, size up."])
    original = P.complete
    P.complete = lambda body, config=None: {"content": "Likely runs small."}
    try:
        result = _with_llm("test-key", lambda: asyncio.run(P.answer_from_page(payload)))
    finally:
        P.complete = original
    assert result["source"] == "page_llm"
    assert result["answer"] == "Likely runs small."


def test_page_prompt_carries_only_page_content_and_the_shared_voice_rules():
    payload = _payload(title="Tee", description="Relaxed fit.",
                       reviews=["Runs small, size up."])
    product = P.build_page_product(payload)
    reviews = P.build_page_reviews(payload)
    conflict = R._detect_conflicts([], reviews, product)
    prompt = P.build_prompt(product, reviews, conflict)
    assert "Runs small, size up." in prompt
    assert "Reviews visible on the page" in prompt
    assert "2 to 3 sentences" in prompt          # shared with the ReAct agent
    assert "Qdrant" not in prompt


def test_page_bullets_stand_in_for_a_missing_description():
    payload = _payload(title="Coat", bullets=["Waterproof membrane", "Knee length"])
    assert "Waterproof membrane" in P.build_page_product(payload)["description"]


def test_page_reviews_are_capped_and_trimmed():
    payload = _payload(reviews=["review %d %s" % (i, "x" * 900) for i in range(40)])
    reviews = P.build_page_reviews(payload)
    assert len(reviews) == P.MAX_REVIEWS
    assert all(len(r["text"]) <= P.MAX_REVIEW_CHARS for r in reviews)


# ── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print("  PASS  %s" % name)
        except Exception as exc:
            failures += 1
            print("  FAIL  %s -> %s: %s" % (name, type(exc).__name__, exc))
    print("\n%d passed, %d failed, %d total" % (len(tests) - failures, failures, len(tests)))
    sys.exit(1 if failures else 0)
