"""eval/appearance_metrics.py

Step 2 of the appearance-description check: score the labelled sheet
eval/annotation/appearance_labels.csv.

Per item, each of kind_ok, colour_ok, upper_ok, fastening_ok and sole_ok is
1 (right), 0 (wrong) or na (the description does not cover it, or the photo
does not show it and the description says so). invented_detail and
zh_matches_en are 1 or 0.

Reported:
    per-aspect accuracy   share of 1s among the items where the aspect is
                          not na
    invented_detail_rate  share of descriptions that state something the
                          photo does not show
    fully_correct         share of descriptions with no 0 in any aspect and
                          no invented detail
    zh_matches_en         share of Chinese texts that say the same thing

The script stops at the first cell that is empty or holds another value.

Usage:
    python eval/appearance_metrics.py
"""

import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASPECTS = ["kind_ok", "colour_ok", "upper_ok", "fastening_ok", "sole_ok"]
BINARY = ["invented_detail", "zh_matches_en"]


def load(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            for col in ASPECTS:
                if row[col].strip().lower() not in ("0", "1", "na"):
                    raise ValueError(f"{path} line {line}, {col}: expected 1, 0 or na, got {row[col]!r}")
            for col in BINARY:
                if row[col].strip() not in ("0", "1"):
                    raise ValueError(f"{path} line {line}, {col}: expected 1 or 0, got {row[col]!r}")
            rows.append({c: row[c].strip().lower() for c in ASPECTS + BINARY})
    return rows


def main():
    rows = load(os.path.join(ROOT, "eval", "annotation", "appearance_labels.csv"))
    n = len(rows)
    result = {"items": n, "aspects": {}}
    for col in ASPECTS:
        judged = [r[col] for r in rows if r[col] != "na"]
        result["aspects"][col] = {
            "accuracy": round(judged.count("1") / len(judged), 3) if judged else None,
            "judged": len(judged),
        }
    result["invented_detail_rate"] = round(sum(r["invented_detail"] == "1" for r in rows) / n, 3)
    result["fully_correct"] = round(
        sum(all(r[c] != "0" for c in ASPECTS) and r["invented_detail"] == "0" for r in rows) / n, 3)
    result["zh_matches_en"] = round(sum(r["zh_matches_en"] == "1" for r in rows) / n, 3)

    with open(os.path.join(ROOT, "eval", "results", "appearance_metrics.json"), "w") as f:
        json.dump(result, f, indent=1)
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
