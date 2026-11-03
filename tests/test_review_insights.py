"""
tests/test_review_insights.py

Covers the parts of the three review features that decide what a shopper
hears, with the language model and Qdrant stubbed out (no network, no
database):

  * highlights — batch proposals are verified review by review, the spoken
    count equals the number of confirmed reviews, disagreement is voiced,
    both languages agree;
  * review Q&A — the count comes from per-review checks, and "I don't know"
    is said when no review is confirmed;
  * cross-product search — ranking order is kept and explanations line up;
  * eval — the number parser reads exactly what the renderer writes, and the
    retrieval metrics are computed correctly.

Run: python -m pytest tests/
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agent.review_insights as RI  # noqa: E402
from eval import check_numbers as CN  # noqa: E402
from eval.retrieval_metrics import score  # noqa: E402
from eval.build_retrieval_pool import BM25  # noqa: E402


def _reviews(asin, n):
    return [
        {"review_id": f"{asin}-{i:02d}", "asin": asin, "title": f"t{i}", "text": f"text {i}", "rating": 5}
        for i in range(1, n + 1)
    ]


PRODUCT = {"asin": "A1", "name": "Test Runner", "n_reviews": 30}


# ── Highlights ───────────────────────────────────────────────────────────────

def test_points_follow_the_most_discussed_aspects():
    tags = {f"A1-{i:02d}": [] for i in range(1, 31)}
    for i in range(1, 13):
        tags[f"A1-{i:02d}"].append("comfortable")
    for i in range(13, 17):
        tags[f"A1-{i:02d}"].append("runs_small")
    for i in range(17, 20):
        tags[f"A1-{i:02d}"].append("true_to_size")
    tags["A1-20"].append("good_grip")  # a single review is not a point

    points = RI.pick_points(tags)

    assert [p["aspect"] for p in points] == ["comfort", "sizing"]
    assert len(points[0]["review_ids"]) == 12
    assert points[1]["stance"] == "runs_small"
    assert points[1]["other"]["stance"] == "true_to_size"


def test_spoken_counts_equal_tagged_reviews_in_both_languages():
    h = {
        "total": 30,
        "points": [{
            "aspect": "sizing", "stance": "runs_small",
            "review_ids": ["A1-01", "A1-02", "A1-03"],
            "other": {"stance": "true_to_size", "review_ids": ["A1-04", "A1-05"]},
        }],
    }
    zh = RI.render_highlights(h, "zh")
    en = RI.render_highlights(h, "en")
    assert "30 条评论里有 3 条提到" in zh["speech"]
    assert "另有 2 条说尺码标准" in zh["speech"]
    assert "3 of 30 reviews mention this" in en["speech"]
    assert "2 say it fits true to size" in en["speech"]
    assert CN.spoken_point_numbers(zh["points"][0]["speech"], "zh") == (30, 3, 2)
    assert CN.spoken_point_numbers(en["points"][0]["speech"], "en") == (30, 3, 2)


def test_proposals_run_in_batches_and_counts_come_from_per_review_checks(monkeypatch):
    seen = []

    def fake_chat_json(messages, schema, **kw):
        keys = list(schema["properties"])
        seen.append(keys)
        return {k: ["comfortable", "comfortable"] for k in keys}  # proposes it for every review

    confirmed = {f"A1-{i:02d}" for i in range(1, 8)}  # but only 7 reviews really say it
    checks = []

    def fake_review_says(review, task):
        checks.append((review["review_id"], task))
        return review["review_id"] in confirmed

    monkeypatch.setattr(RI, "chat_json", fake_chat_json)
    monkeypatch.setattr(RI, "review_says", fake_review_says)
    h = RI.tag_reviews(PRODUCT, _reviews("A1", 25))

    assert [len(k) for k in seen] == [10, 10, 5]           # proposals: 3 batch calls
    assert h["proposed"]["A1-25"] == ["comfortable"]        # duplicates collapse
    assert len(checks) == 25                                # then one check per review
    assert all("comfortable to wear" in task for _, task in checks)
    assert h["checked"]["comfortable"] == sorted(confirmed)
    assert len(h["points"][0]["review_ids"]) == 7           # the count is the verified one
    assert h["tags"]["A1-25"] == []


def test_a_stance_nobody_confirms_is_not_spoken(monkeypatch):
    monkeypatch.setattr(RI, "chat_json", lambda m, schema, **kw: {k: ["runs_small"] for k in schema["properties"]})
    monkeypatch.setattr(RI, "review_says", lambda review, task: False)
    h = RI.tag_reviews(PRODUCT, _reviews("A1", 12))
    assert h["checked"] == {"runs_small": []}
    assert h["points"] == []


def test_tag_schema_only_allows_known_stances(monkeypatch):
    captured = {}

    def fake_chat_json(messages, schema, **kw):
        captured["schema"] = schema
        return {k: [] for k in schema["properties"]}

    monkeypatch.setattr(RI, "chat_json", fake_chat_json)
    RI.tag_reviews(PRODUCT, _reviews("A1", 3))
    items = captured["schema"]["properties"]["1"]["items"]
    assert set(items["enum"]) == set(RI.STANCES)
    assert captured["schema"]["additionalProperties"] is False


def test_no_agreement_is_said_plainly():
    out = RI.render_highlights({"total": 30, "points": []}, "en")
    assert out["points"] == []
    assert "do not agree" in out["speech"]


# ── Review Q&A ───────────────────────────────────────────────────────────────

def _stub_search(monkeypatch, hits):
    monkeypatch.setattr(RI, "_search", lambda query, **kw: {"reviews": hits})
    monkeypatch.setattr(RI, "to_english", lambda text: text)


def _stub_checks(monkeypatch, yes_ids, answer):
    monkeypatch.setattr(RI, "review_says", lambda review, task: review["review_id"] in yes_ids)
    calls = []

    def fake_chat_json(messages, schema, **kw):
        calls.append(messages[-1]["content"])
        return {"answer": answer}

    monkeypatch.setattr(RI, "chat_json", fake_chat_json)
    return calls


def test_answer_count_is_the_number_of_confirmed_reviews(monkeypatch):
    _stub_search(monkeypatch, _reviews("A1", 4))
    calls = _stub_checks(monkeypatch, {"A1-01", "A1-03"}, "Several say it runs narrow.")
    out = RI.answer_question(PRODUCT, "Is it narrow?", "en")
    assert out["count"] == 2
    assert out["answer"] == "Several say it runs narrow. 2 of 30 reviews mention this."
    assert [e["review_id"] for e in out["evidence"]] == ["A1-01", "A1-03"]
    assert "text 2" not in calls[0]  # the answer is written from confirmed reviews only
    assert CN.spoken_answer_numbers(out["answer"], "en") == (30, 2)


def test_no_confirmed_review_means_i_dont_know(monkeypatch):
    _stub_search(monkeypatch, _reviews("A1", 3))
    calls = _stub_checks(monkeypatch, set(), "Probably waterproof.")
    out = RI.answer_question(PRODUCT, "防水吗？", "zh")
    assert out["known"] is False
    assert out["answer"] == "这款鞋的 30 条评论里没有提到这一点，我不知道。"
    assert calls == []  # no answer is generated at all
    assert CN.spoken_answer_numbers(out["answer"], "zh") == (30, 0)


def test_chinese_answer_carries_the_chinese_count(monkeypatch):
    _stub_search(monkeypatch, _reviews("A1", 2))
    _stub_checks(monkeypatch, {"A1-01", "A1-02"}, "有人说偏窄。")
    out = RI.answer_question(PRODUCT, "有没有人说偏窄？", "zh")
    assert out["answer"] == "有人说偏窄。（30 条评论里有 2 条提到）"


# ── Cross-product search ─────────────────────────────────────────────────────

def test_search_keeps_ranking_and_pairs_explanations(monkeypatch):
    ranked = [
        {"asin": "B", "score": 0.9, "reviews": _reviews("B", 1)},
        {"asin": "A", "score": 0.8, "reviews": _reviews("A", 1)},
    ]
    monkeypatch.setattr(RI, "rank_products", lambda q: ranked)
    monkeypatch.setattr(RI, "to_english", lambda text: "shoes for wide feet")
    monkeypatch.setattr(RI, "chat_json", lambda m, schema, **kw: {"products": [
        {"name": "Brand B", "reason": "Roomy toe box."},
        {"name": "Brand A", "reason": "Reviewers with wide feet like it."},
    ]})
    catalogue = {
        a: {"asin": a, "name": f"Shoe {a}", "brand": a, "price": None, "rating": 4.5, "image_url": "x"}
        for a in "AB"
    }
    out = RI.search_products("wide feet", catalogue, "zh")
    assert [r["asin"] for r in out["results"]] == ["B", "A"]
    assert out["results"][0]["reason"] == "Roomy toe box."
    assert out["search_query"] == "shoes for wide feet"
    assert out["speech"].startswith("根据评论，为你找到 2 款：第 1 款，Brand B。")


# ── Query translation ────────────────────────────────────────────────────────

def test_english_query_is_searched_as_is(monkeypatch):
    def no_llm(*a, **kw):
        raise AssertionError("English must not reach the model")
    monkeypatch.setattr(RI, "chat_json", no_llm)
    assert RI.to_english("running shoes for wide feet") == "running shoes for wide feet"


def test_chinese_query_is_translated_before_retrieval(monkeypatch):
    searched = []
    monkeypatch.setattr(RI, "chat_json", lambda m, schema, **kw: {"english": " waterproof hiking boots "})
    monkeypatch.setattr(RI, "_search", lambda query, **kw: searched.append(query) or {"groups": []})
    RI.rank_products("防水的徒步靴")
    assert searched == ["waterproof hiking boots"]


# ── Eval helpers ─────────────────────────────────────────────────────────────

def test_retrieval_metrics():
    relevant = {"q1": {"a", "c"}, "q2": {"z"}, "q3": set()}
    run = {"q1": ["b", "a", "c"], "q2": ["x", "y"], "q3": ["a"]}
    m = score(run, relevant, k=5)
    assert m["recall@5"] == 0.5          # q1: 1.0, q2: 0.0; q3 has no denominator
    assert m["mrr"] == round((0.5 + 0 + 0) / 3, 3)
    assert m["queries_scored_for_recall"] == 2


def test_bm25_needs_the_exact_word():
    reviews = [
        {"asin": "A", "title": "", "text": "great for wide feet, roomy toe box"},
        {"asin": "B", "title": "", "text": "plenty of room for my EE width"},
    ]
    assert BM25(reviews).rank_products("wide feet", 5) == ["A"]


def test_judge_agreement_precision_and_recall():
    from eval.judge_metrics import score as judge_score
    pairs = [
        {"pair": 1, "judge": True, "generator": True},
        {"pair": 2, "judge": True, "generator": None},   # generator never checked this point
        {"pair": 3, "judge": False, "generator": True},
        {"pair": 4, "judge": False, "generator": False},
    ]
    human = {1: True, 2: False, 3: True, 4: False}
    j = judge_score(pairs, human, "judge")
    assert j == {"pairs": 4, "agreement_on_sample": 0.5, "precision": 0.5, "recall": 0.5}
    g = judge_score(pairs, human, "generator")
    assert g == {"pairs": 3, "agreement_on_sample": 1.0, "precision": 1.0, "recall": 1.0}
