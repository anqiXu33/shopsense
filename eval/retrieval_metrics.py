"""eval/retrieval_metrics.py

Step 2 of the retrieval evaluation: read the labelled sheet and score every
system in eval/results/retrieval_runs.json.

    Recall@5  share of the query's relevant products (those labelled 1 in
              the pool) that the system put in its top 5
    MRR       mean of 1 / rank of the first relevant product in the top 5
              (0 when none is relevant)

Relevance is judged only over the pooled candidates (standard pooling, as in
TREC): a relevant product that no system retrieved is unknown, so Recall@5
is recall relative to the pool. Queries with no relevant product in the
pool are reported and left out of Recall (they have no denominator) but
count as 0 in MRR.

Every row needs a label of 1 or 0; the script stops on the first one that
has neither.

Usage:
    python eval/retrieval_metrics.py
"""

import csv
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.join(ROOT, "eval")


def load_labels(path: str) -> dict:
    relevant = defaultdict(set)
    with open(path, encoding="utf-8-sig", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            label = row["label"].strip()
            if label not in ("0", "1"):
                raise ValueError(f"{path} line {i}: label must be 1 or 0, got {label!r}")
            relevant[row["query_id"]]  # every query appears, even with no relevant item
            if label == "1":
                relevant[row["query_id"]].add(row["asin"])
    return relevant


def score(run: dict, relevant: dict, k: int) -> dict:
    recalls, rrs = [], []
    for qid, rel in relevant.items():
        top = run[qid][:k]
        rrs.append(next((1 / r for r, a in enumerate(top, start=1) if a in rel), 0.0))
        if rel:
            recalls.append(len(rel & set(top)) / len(rel))
    return {
        f"recall@{k}": round(sum(recalls) / len(recalls), 3),
        "mrr": round(sum(rrs) / len(rrs), 3),
        "queries_scored_for_recall": len(recalls),
    }


def main():
    relevant = load_labels(os.path.join(EVAL_DIR, "annotation", "retrieval_labels.csv"))
    runs = json.load(open(os.path.join(EVAL_DIR, "results", "retrieval_runs.json")))
    k = runs["k"]

    no_relevant = sorted(q for q, rel in relevant.items() if not rel)
    results = {
        "queries": len(relevant),
        "queries_without_relevant_product": no_relevant,
        "mean_relevant_per_query": round(sum(len(r) for r in relevant.values()) / len(relevant), 2),
        "systems": {name: score(run, relevant, k) for name, run in runs["runs"].items()},
    }
    with open(os.path.join(EVAL_DIR, "results", "retrieval_metrics.json"), "w") as f:
        json.dump(results, f, indent=1)

    print(f"{results['queries']} queries, {results['mean_relevant_per_query']} relevant products per query on average")
    if no_relevant:
        print(f"no relevant product in the pool: {', '.join(no_relevant)}")
    print(f"\n{'system':<16}{'Recall@' + str(k):>10}{'MRR':>8}")
    for name, m in results["systems"].items():
        print(f"{name:<16}{m[f'recall@{k}']:>10.3f}{m['mrr']:>8.3f}")


if __name__ == "__main__":
    sys.exit(main())
