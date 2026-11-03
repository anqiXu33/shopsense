"""agent/review_insights.py

The three review features of the ShopSense store:

  1. Highlights   tag_reviews() first lets the model propose, 10 reviews at
                  a time, which stances (runs small, comfortable …) each
                  review takes. The most common proposals become candidate
                  points, and every candidate is then checked against every
                  review on its own: one call, one review, one yes/no. The
                  spoken count is the number of yes answers. It runs offline
                  (scripts/build_highlights.py); render_highlights() turns
                  the stored result into speech in Chinese or English.
  2. Review Q&A   answer_question() retrieves this product's reviews that
                  relate to a question, asks of each one on its own whether
                  it answers the question, and answers only from those.
  3. Search       search_products() ranks all products by how well their
                  reviews match a need, then explains each pick.

Every count a shopper hears ("12 of 30 reviews mention this") is computed
here by counting per-review yes answers, never written by the model itself,
so the spoken number always equals the evidence behind it. Whether those
reviews really say what was claimed is what eval/check_numbers.py measures,
with a different model as judge.
"""

import asyncio
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from agent.tools.review_search import SemanticReviewSearchTool
from core.llm import chat_json, object_schema

LANGS = ("zh", "en")

ASPECTS = {
    "sizing": {"en": "Sizing", "zh": "尺码"},
    "width": {"en": "Width", "zh": "宽窄"},
    "comfort": {"en": "Comfort", "zh": "舒适度"},
    "support": {"en": "Support", "zh": "支撑"},
    "quality": {"en": "Quality", "zh": "质量"},
    "appearance": {"en": "Look", "zh": "外观"},
    "grip": {"en": "Grip", "zh": "防滑"},
}

# stance -> aspect, what a review must say to earn the tag, spoken text.
STANCES = {
    "runs_small": ("sizing", "the shoe runs small or the reviewer had to size up", "runs small", "尺码偏小"),
    "runs_large": ("sizing", "the shoe runs large or the reviewer had to size down", "runs large", "尺码偏大"),
    "true_to_size": ("sizing", "the shoe fits true to the reviewer's usual size", "fits true to size", "尺码标准"),
    "narrow": ("width", "the shoe is narrow or tight across the foot", "is narrow", "鞋型偏窄"),
    "roomy": ("width", "the shoe is wide or roomy, or works for wide feet", "is roomy and suits wide feet", "鞋型宽松，适合宽脚"),
    "comfortable": ("comfort", "the shoe is comfortable to wear", "is comfortable", "穿着舒服"),
    "uncomfortable": ("comfort", "the shoe is uncomfortable, painful or rubs", "is uncomfortable or rubs", "穿着不舒服或磨脚"),
    "supportive": ("support", "the shoe gives good arch, heel or ankle support", "gives good support", "支撑好"),
    "unsupportive": ("support", "the shoe lacks support or is too flat", "lacks support", "支撑不足"),
    "durable": ("quality", "the shoe is well made or held up well over time", "is well made and durable", "做工好、耐穿"),
    "poor_quality": ("quality", "the shoe fell apart, wore out fast or arrived defective", "wears out or breaks quickly", "容易坏或磨损快"),
    "looks_good": ("appearance", "the shoe looks good or matches the photos", "looks good", "外观好看"),
    "looks_bad": ("appearance", "the shoe looks worse than expected or unlike the photos", "looks worse than expected", "外观不如预期"),
    "good_grip": ("grip", "the sole grips well and is not slippery", "grips well", "防滑好"),
    "slippery": ("grip", "the sole is slippery", "is slippery", "鞋底打滑"),
}

TAG_BATCH = 10         # reviews per proposal call
N_POINTS = 3           # key points spoken per product
N_CANDIDATE_ASPECTS = N_POINTS + 1  # aspects whose stances are verified review by review
MIN_POINT_REVIEWS = 2  # a stance needs at least this many reviews to be spoken
QA_TOP_K = 10          # reviews retrieved per question
SEARCH_TOP_PRODUCTS = 5
SEARCH_REVIEWS_PER_PRODUCT = 3
SEARCH_MIN_RATING = 4  # recommendations are argued from satisfied buyers

# Per-review yes/no checks run in parallel; one pool shared by all callers.
_CHECKS = ThreadPoolExecutor(32)
_YES_NO = object_schema({"answer": {"type": "string", "enum": ["yes", "no"]}})


@lru_cache(maxsize=1)
def _review_tool() -> SemanticReviewSearchTool:
    # Created on first use: opening Qdrant locks a local-mode store, and the
    # offline highlights builder never needs it.
    return SemanticReviewSearchTool()


def _numbered(reviews: list) -> str:
    return "\n".join(
        f"[{i}] ({r['rating']} stars) {r['title']}. {r['text']}"
        for i, r in enumerate(reviews, start=1)
    )


def review_says(review: dict, task: str) -> bool:
    """Ask about one review, alone: does it say this / answer this? yes or no."""
    out = chat_json(
        [{"role": "system", "content": "You check customer reviews carefully and literally. Reply with JSON only."},
         {"role": "user", "content": (
             f"Customer review of a shoe ({review['rating']} stars):\n"
             f"\"{review['title']}. {review['text']}\"\n\n"
             f"{task}\nAnswer yes or no."
         )}],
        schema=_YES_NO,
    )
    return out["answer"] == "yes"


def reviews_saying(reviews: list, task: str) -> list:
    """The reviews for which review_says() is yes, checked in parallel."""
    verdicts = _CHECKS.map(lambda r: review_says(r, task), reviews)
    return [r for r, yes in zip(reviews, verdicts) if yes]


def stance_task(stance: str) -> str:
    return f"Does this review clearly say that {STANCES[stance][1]}?"


# ── 1. Highlights ────────────────────────────────────────────────────────────

_STANCE_GUIDE = "\n".join(f"- {k}: {v[1]}" for k, v in STANCES.items())


def _tag_batch(product: dict, batch: list) -> list:
    prompt = (
        f"Product: {product['name']}\n\n"
        f"Reviews:\n{_numbered(batch)}\n\n"
        "For every review, list the tags whose statement the review clearly makes "
        "about this shoe. A review can have several tags or none. Do not tag "
        "something the review does not say.\n\n"
        f"Tags:\n{_STANCE_GUIDE}\n\n"
        f"Reply with one key per review, \"1\" to \"{len(batch)}\", e.g. "
        '{"1": ["runs_small", "comfortable"], "2": []}'
    )
    tag_list = {"type": "array", "items": {"type": "string", "enum": list(STANCES)}, "maxItems": 5}
    out = chat_json(
        [{"role": "system", "content": "You label customer reviews. Reply with JSON only."},
         {"role": "user", "content": prompt}],
        schema=object_schema({str(i): tag_list for i in range(1, len(batch) + 1)}),
    )
    return [sorted(set(out[str(i)])) for i in range(1, len(batch) + 1)]


def tag_reviews(product: dict, reviews: list) -> dict:
    """
    Propose stances in batches, verify the candidates review by review, and
    keep the most common verified stances as key points.

    Stored: the batch proposals (for inspection only), the verified yes-sets
    per checked stance, and the points built from the verified tags.
    """
    proposed = {}
    for start in range(0, len(reviews), TAG_BATCH):
        batch = reviews[start:start + TAG_BATCH]
        for r, t in zip(batch, _tag_batch(product, batch)):
            proposed[r["review_id"]] = t

    candidates = sorted({
        stance
        for p in pick_points(proposed, N_CANDIDATE_ASPECTS)
        for stance in [p["stance"]] + ([p["other"]["stance"]] if p["other"] else [])
    })
    checked = {stance: sorted(r["review_id"] for r in reviews_saying(reviews, stance_task(stance)))
               for stance in candidates}

    verified = {r["review_id"]: [] for r in reviews}
    for stance, rids in checked.items():
        for rid in rids:
            verified[rid].append(stance)
    return {
        "total": len(reviews),
        "proposed": proposed,
        "checked": checked,
        "tags": verified,
        "points": pick_points(verified),
    }


def pick_points(tags: dict, n_points: int = N_POINTS) -> list:
    """
    One point per aspect, for the n_points aspects most reviews talk about.

    The point states the stance most of those reviews take; if another stance
    on the same aspect has support too ("runs small" vs "true to size"), it
    is kept so the shopper hears the disagreement.
    """
    by_stance = {}
    for rid, ts in tags.items():
        for t in ts:
            by_stance.setdefault(t, []).append(rid)
    aspect_total = Counter()
    for stance, rids in by_stance.items():
        aspect_total[STANCES[stance][0]] += len(rids)

    points = []
    for aspect, _ in sorted(aspect_total.items(), key=lambda x: (-x[1], x[0])):
        ranked = sorted(
            ((s, r) for s, r in by_stance.items() if STANCES[s][0] == aspect),
            key=lambda x: (-len(x[1]), x[0]),
        )
        main, main_ids = ranked[0]
        if len(main_ids) < MIN_POINT_REVIEWS:
            continue
        other = None
        if len(ranked) > 1 and len(ranked[1][1]) >= MIN_POINT_REVIEWS:
            other = {"stance": ranked[1][0], "review_ids": sorted(ranked[1][1])}
        points.append({"aspect": aspect, "stance": main, "review_ids": sorted(main_ids), "other": other})
        if len(points) == n_points:
            break
    return points


def count_phrase(k: int, n: int, lang: str) -> str:
    if lang == "zh":
        return f"{n} 条评论里有 {k} 条提到"
    return f"{k} of {n} reviews mention this"


def _stance_text(stance: str, lang: str) -> str:
    return STANCES[stance][3] if lang == "zh" else STANCES[stance][2]


def render_highlights(highlights: dict, lang: str) -> dict:
    n = highlights["total"]
    points = []
    for p in highlights["points"]:
        k = len(p["review_ids"])
        label = ASPECTS[p["aspect"]][lang]
        count = count_phrase(k, n, lang)
        if lang == "zh":
            text = _stance_text(p["stance"], lang)
            extra = f"，另有 {len(p['other']['review_ids'])} 条说{_stance_text(p['other']['stance'], lang)}" if p["other"] else ""
            detail = f"{text}（{count}{extra}）。"
            speech = f"{label}：{detail}"
        else:
            text = "It " + _stance_text(p["stance"], lang)
            extra = (f" {len(p['other']['review_ids'])} say it {_stance_text(p['other']['stance'], lang)}."
                     if p["other"] else "")
            detail = f"{text}. {count.capitalize()}.{extra}"
            speech = f"{label}: {detail}"
        points.append({
            "aspect": p["aspect"],
            "label": label,
            "text": text,
            "detail": detail,
            "count": k,
            "total": n,
            "speech": speech,
            "review_ids": p["review_ids"],
            "other": p["other"],
        })
    if points:
        intro = "评论要点：" if lang == "zh" else "Review highlights. "
        speech = intro + " ".join(p["speech"] for p in points)
    else:
        speech = (f"这款鞋的 {n} 条评论没有形成明显的共同看法。" if lang == "zh"
                  else f"The {n} reviews of this shoe do not agree on any point.")
    return {"points": points, "speech": speech}


# ── Retrieval ────────────────────────────────────────────────────────────────

_CJK = re.compile(r"[\u4e00-\u9fff]")


def to_english(text: str) -> str:
    """
    Translate a Chinese query into English before it is embedded.

    The reviews are English, and a small multilingual embedding model places
    a Chinese need far from the English reviews that describe it ("防水的徒步靴"
    retrieved sneakers and water shoes). Searching in the reviews' own
    language avoids that. English queries go through untouched.
    """
    if not _CJK.search(text):
        return text
    out = chat_json(
        [{"role": "system", "content": "You translate shoppers' requests about shoes. Reply with JSON only."},
         {"role": "user", "content": (
             "Translate this request into short, natural English, phrased the way "
             f"a shopper would say it. Keep every detail and add nothing.\n\n{text}"
         )}],
        schema=object_schema({"english": {"type": "string"}}),
    )
    return out["english"].strip()


def _search(query: str, **kwargs) -> dict:
    result = asyncio.run(_review_tool().execute(query=query, **kwargs))
    if not result.success:
        raise RuntimeError(result.error_message)
    return result.data


# ── 2. Review Q&A ────────────────────────────────────────────────────────────

def answer_question(product: dict, question: str, lang: str) -> dict:
    """Answer from this product's reviews only; say so when they are silent."""
    n = product["n_reviews"]
    hits = _search(to_english(question), asin=product["asin"], top_k=QA_TOP_K)["reviews"]
    evidence = reviews_saying(
        hits,
        f"Does this review contain information that directly answers the question "
        f"\"{question}\"? Sharing a word with the question is not enough.",
    )
    language = "Chinese" if lang == "zh" else "English"
    k = len(evidence)
    if k == 0:
        answer = (
            f"这款鞋的 {n} 条评论里没有提到这一点，我不知道。"
            if lang == "zh" else
            f"None of the {n} reviews of this shoe mention this, so I don't know."
        )
    else:
        count = count_phrase(k, n, lang)
        out = chat_json(
            [{"role": "system", "content": "You answer shoppers' questions strictly from customer reviews. Reply with JSON only."},
             {"role": "user", "content": (
                 f"Product: {product['name']}\n"
                 f"Shopper's question: {question}\n\n"
                 f"Reviews that answer it:\n{_numbered(evidence)}\n\n"
                 f"Answer the question in {language} in one or two short sentences, "
                 "using only these reviews; say so if they disagree. Do not mention "
                 "review numbers or counts."
             )}],
            schema=object_schema({"answer": {"type": "string"}}),
        )
        body = out["answer"].strip()
        answer = f"{body}（{count}）" if lang == "zh" else f"{body.rstrip('.')}. {count.capitalize()}."
    return {
        "answer": answer,
        "count": k,
        "total": n,
        "known": k > 0,
        "evidence": [
            {"review_id": r["review_id"], "rating": r["rating"], "text": r["text"]} for r in evidence
        ],
    }


# ── 3. Cross-product search ──────────────────────────────────────────────────

def rank_products(query: str, min_rating: int | None = SEARCH_MIN_RATING,
                  limit: int = SEARCH_TOP_PRODUCTS) -> list:
    """
    Rank products by their best-matching reviews (Qdrant group-by on asin).
    A Chinese query is translated to English first (see to_english).

    Returns [{"asin", "score", "reviews": [...]}], best first. The score of a
    product is the similarity of its single best review, which is how Qdrant
    orders groups.
    """
    filters = {"verified_only": False}
    if min_rating is not None:
        filters["rating_min"] = min_rating
    data = _search(
        to_english(query),
        filters=filters,
        top_k=limit,
        group_by_asin=True,
        group_size=SEARCH_REVIEWS_PER_PRODUCT,
    )
    return [
        {"asin": g["asin"], "score": g["reviews"][0]["relevance_score"], "reviews": g["reviews"]}
        for g in data["groups"]
    ]


def search_products(query: str, products: dict, lang: str) -> dict:
    """Recommend the best-matching products and say why, from their reviews."""
    search_query = to_english(query)
    ranked = rank_products(search_query)
    language = "Chinese" if lang == "zh" else "English"
    blocks = []
    for i, r in enumerate(ranked, start=1):
        quotes = "\n".join(f'  - "{rv["text"][:300]}"' for rv in r["reviews"])
        blocks.append(f"Product {i}: {products[r['asin']]['name']}\n{quotes}")
    prompt = (
        f"Shopper's need: {query}\n\n" + "\n\n".join(blocks) + "\n\n"
        f"For each product, in {language}: give a short spoken name (brand and "
        "model, at most 6 words) and one sentence (at most 25 words) on why it "
        "fits the need, based only on the quoted reviews. If the quotes show it "
        "does not fit, say that honestly.\n\n"
    )
    item = object_schema({"name": {"type": "string"}, "reason": {"type": "string"}})
    out = chat_json(
        [{"role": "system", "content": "You explain shoe recommendations from customer reviews. Reply with JSON only."},
         {"role": "user", "content": prompt}],
        schema=object_schema({"products": {
            "type": "array", "items": item, "minItems": len(ranked), "maxItems": len(ranked),
        }}),
    )

    results = []
    for i, (r, e) in enumerate(zip(ranked, out["products"]), start=1):
        p = products[r["asin"]]
        results.append({
            "rank": i,
            "asin": r["asin"],
            "name": p["name"],
            "short_name": e["name"].strip(),
            "brand": p["brand"],
            "price": p["price"],
            "rating": p["rating"],
            "image_url": p["image_url"],
            "score": round(r["score"], 4),
            "reason": e["reason"].strip(),
            "evidence": [
                {"review_id": rv["review_id"], "rating": rv["rating"], "text": rv["text"]}
                for rv in r["reviews"]
            ],
        })

    if lang == "zh":
        lines = [f"第 {x['rank']} 款，{x['short_name']}。{x['reason']}" for x in results]
        speech = f"根据评论，为你找到 {len(results)} 款：" + " ".join(lines) + " 说出“打开第几款”查看详情。"
    else:
        lines = [f"Number {x['rank']}, {x['short_name']}. {x['reason']}" for x in results]
        speech = (f"Based on reviews, here are {len(results)} matches. " + " ".join(lines)
                  + " Say 'open number' and a number to hear more.")
    return {"query": query, "search_query": search_query, "results": results, "speech": speech}
