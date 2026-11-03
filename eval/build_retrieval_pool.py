"""eval/build_retrieval_pool.py

Step 1 of the retrieval evaluation: run every cross-product search system on
the 30 queries in eval/queries.json, pool their top-5 products, and export
one row per (query, candidate product) for a human to label.

Systems compared (all rank products by their best-matching review):
    bm25_en        keyword BM25 over all reviews, English query (baseline)
    vector_en_all  Qdrant vector search over all reviews, English query
    vector_en      Qdrant vector search over 4-5 star reviews, English query
                   (what the store uses)
    vector_zh      the store's system, Chinese query

Outputs:
    eval/results/retrieval_runs.json           ranked top-5 per system and query
    eval/annotation/retrieval_labels.csv       the sheet to label (UTF-8 with BOM,
                                               opens correctly in Excel and Numbers)

The label column is left empty: fill it with 1 (fits the need) or 0 (does
not), then run eval/retrieval_metrics.py. Rerunning this script overwrites
the sheet, so do not rerun it after you start labelling.

Stop the backend first when Qdrant runs in local mode (QDRANT_PATH).

Usage:
    python eval/build_retrieval_pool.py
"""

import csv
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_client.models import FieldCondition, Filter, MatchValue

from agent.review_insights import SEARCH_TOP_PRODUCTS, rank_products
from config.settings import QDRANT_COLLECTIONS, ROOT_DIR, get_qdrant_client
from core.embeddings import embed

EVAL_DIR = os.path.join(ROOT_DIR, "eval")
K = SEARCH_TOP_PRODUCTS
SNIPPETS = 3
SNIPPET_CHARS = 350


# ── BM25 baseline ────────────────────────────────────────────────────────────

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = set("a an and are as at be but by for from has have i in is it its of on or "
            "so that the their them they this to was were with you your my me".split())


def tokenize(text: str) -> list:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


class BM25:
    def __init__(self, reviews: list, k1: float = 1.5, b: float = 0.75):
        self.reviews = reviews
        self.docs = [Counter(tokenize(f"{r['title']} {r['text']}")) for r in reviews]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lens) / len(self.lens)
        df = Counter(t for d in self.docs for t in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.k1, self.b = k1, b

    def rank_products(self, query: str, limit: int) -> list:
        terms = tokenize(query)
        best = {}
        for doc, length, r in zip(self.docs, self.lens, self.reviews):
            score = 0.0
            for t in terms:
                f = doc.get(t)
                if f:
                    score += self.idf[t] * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * length / self.avg))
            if score > best.get(r["asin"], 0.0):
                best[r["asin"]] = score
        return [a for a, _ in sorted(best.items(), key=lambda x: (-x[1], x[0]))[:limit]]


# ── Pooling ──────────────────────────────────────────────────────────────────

def snippets(client, asin: str, query: str) -> list:
    """The candidate's reviews closest to the need, to help the annotator."""
    hits = client.query_points(
        collection_name=QDRANT_COLLECTIONS["reviews"],
        query=embed(query),
        query_filter=Filter(must=[FieldCondition(key="asin", match=MatchValue(value=asin))]),
        limit=SNIPPETS,
        with_payload=True,
    ).points
    return [f"({h.payload['rating']}★) {h.payload['text'][:SNIPPET_CHARS]}" for h in hits]


def main():
    queries = json.load(open(os.path.join(EVAL_DIR, "queries.json")))
    products = {p["asin"]: p for p in json.load(open(os.path.join(ROOT_DIR, "data", "shoes", "products.json")))}
    reviews = json.load(open(os.path.join(ROOT_DIR, "data", "shoes", "reviews.json")))
    bm25 = BM25(reviews)

    runs = defaultdict(dict)
    for q in queries:
        runs["bm25_en"][q["id"]] = bm25.rank_products(q["en"], K)
        runs["vector_en_all"][q["id"]] = [r["asin"] for r in rank_products(q["en"], min_rating=None, limit=K)]
        runs["vector_en"][q["id"]] = [r["asin"] for r in rank_products(q["en"], limit=K)]
        runs["vector_zh"][q["id"]] = [r["asin"] for r in rank_products(q["zh"], limit=K)]
        print(f"{q['id']} ranked")

    with open(os.path.join(EVAL_DIR, "results", "retrieval_runs.json"), "w") as f:
        json.dump({"k": K, "runs": runs}, f, indent=1)

    client = get_qdrant_client()
    rows = []
    for q in queries:
        pool = sorted({a for system in runs.values() for a in system[q["id"]]})
        for asin in pool:
            p = products[asin]
            s = snippets(client, asin, q["en"])
            rows.append({
                "query_id": q["id"],
                "query_en": q["en"],
                "query_zh": q["zh"],
                "asin": asin,
                "product": p["name"],
                "category": " > ".join([p["gender"], *p["category_path"]]),
                "review_1": s[0], "review_2": s[1], "review_3": s[2],
                "label": "",
            })

    path = os.path.join(EVAL_DIR, "annotation", "retrieval_labels.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows for {len(queries)} queries -> {path}")


if __name__ == "__main__":
    main()
