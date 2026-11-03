"""eval/judge_metrics.py

Step 2 of checking the judge: compare the human labels in
eval/annotation/judge_labels.csv with the model verdicts kept in
eval/results/judge_sample.json.

For each model that decided a pair (the judge, the generator's per-review
check, the earlier gpt-6-luna judge):

    agreement_on_sample  share of pairs where the model matches the human,
                         on the 25-yes / 25-no sample as drawn
    agreement_weighted   the same, with the judge-yes and judge-no halves
                         reweighted to how often the judge says yes over all
                         its highlight judgments; this estimates agreement
                         on judgments as they actually occur (judge only)
    precision            of the pairs the model said yes to, share the human
                         also said yes to
    recall               of the pairs the human said yes to, share the model
                         also said yes to

Every row needs a label of 1 or 0; the script stops at the first that has
neither.

Usage:
    python eval/judge_metrics.py
"""

import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_labels(path: str) -> dict:
    labels = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            if row["label"].strip() not in ("0", "1"):
                raise ValueError(f"{path} line {line}: label must be 1 or 0, got {row['label']!r}")
            labels[int(row["pair"])] = row["label"].strip() == "1"
    return labels


def score(pairs: list, labels: dict, model: str) -> dict:
    decided = [p for p in pairs if p[model] is not None]
    agree = [p[model] == labels[p["pair"]] for p in decided]
    said_yes = [p for p in decided if p[model]]
    human_yes = [p for p in decided if labels[p["pair"]]]
    return {
        "pairs": len(decided),
        "agreement_on_sample": round(sum(agree) / len(decided), 3),
        "precision": round(sum(labels[p["pair"]] for p in said_yes) / len(said_yes), 3) if said_yes else None,
        "recall": round(sum(p[model] for p in human_yes) / len(human_yes), 3) if human_yes else None,
    }


def main():
    labels = load_labels(os.path.join(ROOT, "eval", "annotation", "judge_labels.csv"))
    sample = json.load(open(os.path.join(ROOT, "eval", "results", "judge_sample.json")))
    pairs = sample["pairs"]

    result = {
        "human_yes": sum(labels.values()),
        "pairs": len(labels),
        "models": {
            f"judge ({sample['judge_model']})": score(pairs, labels, "judge"),
            "generator per-review check (gpt-6-luna)": score(pairs, labels, "generator"),
            f"earlier judge ({sample['earlier_judge']})": score(pairs, labels, "earlier_judge"),
        },
    }

    # Reweight the judge's agreement to its real yes-rate.
    yes_half = [p for p in pairs if p["judge"]]
    no_half = [p for p in pairs if not p["judge"]]
    acc_yes = sum(labels[p["pair"]] for p in yes_half) / len(yes_half)
    acc_no = sum(not labels[p["pair"]] for p in no_half) / len(no_half)
    rate = sample["judge_yes_rate"]
    result["models"][f"judge ({sample['judge_model']})"]["agreement_weighted"] = round(
        rate * acc_yes + (1 - rate) * acc_no, 3)
    result["judge_yes_rate"] = rate

    with open(os.path.join(ROOT, "eval", "results", "judge_metrics.json"), "w") as f:
        json.dump(result, f, indent=1)
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
