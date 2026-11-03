"""eval/check_numbers.py

Check the numbers ShopSense speaks ("30 条评论里有 12 条提到" /
"12 of 30 reviews mention this") against the reviews themselves.

Two sources of numbers are checked:

  highlights  30 products sampled with a fixed seed. Every count spoken in
              the Chinese and the English highlights, including the "另有 N
              条说…" / "N say it…" counter-view.
  review Q&A  30 (product, question) pairs: 15 more products × 2 questions
              from a fixed bank, half asked in Chinese and half in English,
              run through the live answer_question() pipeline.

Ground truth. For every claim, a judge model reads each of the product's
reviews on its own and answers yes or no: does this review make the claim
(highlights) / answer the question (Q&A)? The true count is the number of
yes answers. Judging one review at a time is a different, simpler task than
the generator's batch tagging, but it is still a language model: set
JUDGE_MODEL (and JUDGE_BASE_URL / JUDGE_API_KEY) to a different model to reduce self-agreement, and see the README
for the limits of this check.

Numbers are parsed with regular expressions from the text a shopper hears,
not taken from internal fields, so a rendering bug would show up as a
mismatch too.

Metrics (per source):
    denominator_correct  spoken total N equals the product's review count
    exact                spoken count equals the true count
    within_1             off by at most one review
    citation_precision   share of the reviews behind a spoken count that the
                         judge confirms
    citation_recall      share of the judge-confirmed reviews that were counted
    Q&A only:
    unknown_correct      "the reviews don't mention this" said when the true
                         count is 0, out of all "don't know" answers
    missed_unknown       "don't know" said although some review answers it

Judgments are cached in eval/results/judgments.json, so an interrupted run
resumes. Stop the backend first when Qdrant runs in local mode.

Usage:
    python eval/check_numbers.py
"""

import json
import os
import random
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.review_insights import STANCES, answer_question, render_highlights
from config.settings import JUDGE, ROOT_DIR
from core.llm import chat_json, object_schema, usage_summary

RESULTS = os.path.join(ROOT_DIR, "eval", "results")
JUDGMENTS = os.path.join(RESULTS, "judgments.json")
N_HIGHLIGHT_PRODUCTS = 30
N_QA_PRODUCTS = 15
SEED = 2026
CONCURRENCY = 10

QUESTIONS = [
    ("Does it run small?", "尺码偏小吗？"),
    ("Has anyone said it is narrow?", "有没有人说偏窄？"),
    ("Is it comfortable for standing all day?", "整天站着穿舒服吗？"),
    ("Does the sole wear out quickly?", "鞋底容易磨坏吗？"),
    ("Is it good for wide feet?", "适合宽脚吗？"),
    ("Is it waterproof?", "防水吗？"),
    ("Does it squeak when you walk?", "走路会吱吱响吗？"),
    ("Does it have a strong smell when new?", "新鞋有很重的味道吗？"),
    ("Is it slippery on wet floors?", "在湿地面上打滑吗？"),
    ("Does it help with back pain?", "对腰背痛有帮助吗？"),
]

# ── Parsing what the shopper hears ───────────────────────────────────────────

ZH_COUNT = re.compile(r"(\d+) 条评论里有 (\d+) 条提到")
ZH_OTHER = re.compile(r"另有 (\d+) 条说")
EN_COUNT = re.compile(r"(\d+) of (\d+) reviews mention this")
EN_OTHER = re.compile(r"(\d+) say it")
ZH_UNKNOWN = re.compile(r"这款鞋的 (\d+) 条评论里没有提到这一点")
EN_UNKNOWN = re.compile(r"None of the (\d+) reviews of this shoe mention this")


def spoken_point_numbers(speech: str, lang: str) -> tuple:
    """(total, count, other_count or None) from one highlight sentence."""
    if lang == "zh":
        n, k = map(int, ZH_COUNT.search(speech).groups())
        other = ZH_OTHER.search(speech)
    else:
        k, n = map(int, EN_COUNT.search(speech).groups())
        other = EN_OTHER.search(speech)
    return n, k, int(other.group(1)) if other else None


def spoken_answer_numbers(answer: str, lang: str) -> tuple:
    """(total, count) from a Q&A answer; count is 0 for "don't know"."""
    unknown = (ZH_UNKNOWN if lang == "zh" else EN_UNKNOWN).search(answer)
    if unknown:
        return int(unknown.group(1)), 0
    if lang == "zh":
        n, k = map(int, ZH_COUNT.search(answer).groups())
    else:
        k, n = map(int, EN_COUNT.search(answer).groups())
    return n, k


# ── Judge ────────────────────────────────────────────────────────────────────

_YES_NO = object_schema({"answer": {"type": "string", "enum": ["yes", "no"]}})


class Judge:
    """
    One yes/no question per review. All reviews of a claim are judged in
    parallel; answers are cached on disk, keyed by judge model, task and
    review, so reruns and other claims about the same stance reuse them.
    """

    def __init__(self):
        self.cache = json.load(open(JUDGMENTS)) if os.path.exists(JUDGMENTS) else {}
        self.pool = ThreadPoolExecutor(CONCURRENCY)

    def _ask(self, review: dict, task: str) -> bool:
        prompt = (
            f"Customer review of a shoe ({review['rating']} stars):\n"
            f"\"{review['title']}. {review['text']}\"\n\n"
            f"{task}\nAnswer yes or no."
        )
        out = chat_json(
            [{"role": "system", "content": "You check customer reviews carefully and literally. Reply with JSON only."},
             {"role": "user", "content": prompt}],
            schema=_YES_NO, config=JUDGE,
        )
        return out["answer"] == "yes"

    def confirmed(self, reviews: list, kind: str, subject: str, task: str) -> set:
        """IDs of the reviews the judge says make the claim / answer the question."""
        keys = {r["review_id"]: f"{JUDGE.model}|{kind}|{subject}|{r['review_id']}" for r in reviews}
        missing = [r for r in reviews if keys[r["review_id"]] not in self.cache]
        for r, verdict in zip(missing, self.pool.map(lambda r: self._ask(r, task), missing)):
            self.cache[keys[r["review_id"]]] = verdict
        if missing:
            self.save()
        return {rid for rid, key in keys.items() if self.cache[key]}

    def save(self):
        with open(JUDGMENTS + ".tmp", "w") as f:
            json.dump(self.cache, f)
        os.replace(JUDGMENTS + ".tmp", JUDGMENTS)

    def stance(self, reviews: list, stance: str) -> set:
        return self.confirmed(reviews, "stance", stance,
                              f"Does this review clearly say that {STANCES[stance][1]}?")

    def answers(self, reviews: list, question: str) -> set:
        return self.confirmed(
            reviews, "qa", question,
            f"Does this review contain information that directly answers the "
            f"question \"{question}\"? Sharing a word with the question is not enough.",
        )


# ── Scoring ──────────────────────────────────────────────────────────────────

def compare(stated: int, cited: set, truth: set) -> dict:
    return {
        "stated": stated,
        "true": len(truth),
        "exact": stated == len(truth),
        "within_1": abs(stated - len(truth)) <= 1,
        "cited_confirmed": len(cited & truth),
        "cited": len(cited),
        "missed": len(truth - cited),
    }


def summarize(claims: list) -> dict:
    n = len(claims)
    cited = sum(c["cited"] for c in claims)
    true = sum(c["true"] for c in claims)
    confirmed = sum(c["cited_confirmed"] for c in claims)
    return {
        "claims": n,
        "denominator_correct": round(sum(c["denominator_ok"] for c in claims) / n, 3),
        "exact": round(sum(c["exact"] for c in claims) / n, 3),
        "within_1": round(sum(c["within_1"] for c in claims) / n, 3),
        "citation_precision": round(confirmed / cited, 3) if cited else None,
        "citation_recall": round(confirmed / true, 3) if true else None,
        "mean_abs_error": round(sum(abs(c["stated"] - c["true"]) for c in claims) / n, 2),
    }


def check_highlights(products: list, reviews: dict, highlights: dict, judge: Judge) -> list:
    claims = []
    for p in products:
        rs = reviews[p["asin"]]
        h = highlights[p["asin"]]
        for lang in ("zh", "en"):
            for point, rendered in zip(h["points"], render_highlights(h, lang)["points"]):
                n, k, k_other = spoken_point_numbers(rendered["speech"], lang)
                parts = [(point["stance"], k, point["review_ids"])]
                if point["other"]:
                    parts.append((point["other"]["stance"], k_other, point["other"]["review_ids"]))
                for stance, stated, cited in parts:
                    truth = judge.stance(rs, stance)
                    claims.append({
                        "asin": p["asin"], "lang": lang, "stance": stance,
                        "speech": rendered["speech"],
                        "denominator_ok": n == len(rs),
                        **compare(stated, set(cited), truth),
                        "cited_ids": sorted(cited),
                        "true_ids": sorted(truth),
                    })
    return claims


def check_qa(products: list, reviews: dict, judge: Judge) -> list:
    claims = []
    for i in range(2 * len(products)):
        p = products[i // 2]
        q_en, q_zh = QUESTIONS[i % len(QUESTIONS)]
        lang = "zh" if i % 2 == 0 else "en"
        out = answer_question(p, q_zh if lang == "zh" else q_en, lang)
        n, k = spoken_answer_numbers(out["answer"], lang)
        rs = reviews[p["asin"]]
        truth = judge.answers(rs, q_en)
        cited = {e["review_id"] for e in out["evidence"]}
        claims.append({
            "asin": p["asin"], "lang": lang, "question": q_zh if lang == "zh" else q_en,
            "answer": out["answer"],
            "denominator_ok": n == len(rs),
            **compare(k, cited, truth),
            "cited_ids": sorted(cited),
            "true_ids": sorted(truth),
        })
        print(f"  Q&A {i + 1}/{2 * len(products)}: stated {k}, true {len(truth)}")
    return claims


def main():
    shoes = os.path.join(ROOT_DIR, "data", "shoes")
    products = json.load(open(os.path.join(shoes, "products.json")))
    highlights = json.load(open(os.path.join(shoes, "highlights.json")))
    reviews = defaultdict(list)
    for r in json.load(open(os.path.join(shoes, "reviews.json"))):
        reviews[r["asin"]].append(r)

    sample = random.Random(SEED).sample(products, N_HIGHLIGHT_PRODUCTS + N_QA_PRODUCTS)
    judge = Judge()

    print(f"Highlights: {N_HIGHLIGHT_PRODUCTS} products (judge: {JUDGE.model})")
    hl = check_highlights(sample[:N_HIGHLIGHT_PRODUCTS], reviews, highlights, judge)
    print(f"Review Q&A: {2 * N_QA_PRODUCTS} questions")
    qa = check_qa(sample[N_HIGHLIGHT_PRODUCTS:], reviews, judge)

    unknown = [c for c in qa if c["stated"] == 0]
    qa_summary = summarize(qa)
    qa_summary["unknown_answers"] = len(unknown)
    qa_summary["unknown_correct"] = sum(c["true"] == 0 for c in unknown)
    qa_summary["missed_unknown"] = sum(c["true"] > 0 for c in unknown)

    # zh and en highlights share counts, so score one language for the headline
    # number and keep the other as a rendering check.
    summary = {
        "judge_model": JUDGE.model,
        "llm_usage": usage_summary(),
        "highlights": summarize([c for c in hl if c["lang"] == "en"]),
        "highlights_zh_matches_en": all(
            a["stated"] == b["stated"]
            for a, b in zip([c for c in hl if c["lang"] == "zh"], [c for c in hl if c["lang"] == "en"])
        ),
        "qa": qa_summary,
    }
    with open(os.path.join(RESULTS, "number_check.json"), "w") as f:
        json.dump({"summary": summary, "highlights": hl, "qa": qa}, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
