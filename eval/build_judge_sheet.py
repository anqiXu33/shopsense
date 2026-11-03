"""eval/build_judge_sheet.py

Step 1 of checking the judge: sample 50 (review, highlight point) pairs that
the judge of eval/check_numbers.py decided on, and export them for a person
to label: does this review make this point, yes or no?

The sample is stratified: 25 pairs the judge said yes to and 25 it said no
to, drawn with a fixed seed from the highlight judgments of the current
judge model (JUDGE_MODEL). Yes is the rarer verdict, so a plain random sample
would hold only a handful of yes pairs; with 25 of each, both the judge's
false alarms and its misses can be measured. eval/judge_metrics.py reweights
the two halves by how often the judge says yes overall.

The sheet does not show any model's verdict. The verdicts are kept apart in
eval/results/judge_sample.json: the judge's, the generator's per-review
check where it checked the same point, and the earlier gpt-6-luna judge's
where it judged the same pair.

Outputs:
    eval/annotation/judge_labels.csv     the sheet to label (UTF-8 with BOM)
    eval/results/judge_sample.json       hidden model verdicts for the 50 pairs

Rerunning overwrites both, so do not rerun after you start labelling.

Usage:
    python eval/build_judge_sheet.py      (after eval/check_numbers.py)
"""

import csv
import json
import os
import random
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.review_insights import STANCES
from config.settings import JUDGE, ROOT_DIR

PER_VERDICT = 25
SEED = 2026
EARLIER_JUDGE = "gpt-6-luna"

# The statement a review must make, in Chinese, for the annotator.
STATEMENT_ZH = {
    "runs_small": "鞋子偏小，或者评论者买大了一码",
    "runs_large": "鞋子偏大，或者评论者买小了一码",
    "true_to_size": "鞋子按评论者平时的尺码买正合适",
    "narrow": "鞋子偏窄，或者脚面/脚掌处紧",
    "roomy": "鞋子宽松、空间大，或者适合宽脚",
    "comfortable": "鞋子穿着舒服",
    "uncomfortable": "鞋子穿着不舒服、疼或者磨脚",
    "supportive": "鞋子对足弓、脚跟或脚踝的支撑好",
    "unsupportive": "鞋子缺乏支撑，或者太平",
    "durable": "鞋子做工好，或者穿了很久依然完好",
    "poor_quality": "鞋子开胶散架、磨损很快，或者收到时就有缺陷",
    "looks_good": "鞋子好看，或者和图片一致",
    "looks_bad": "鞋子比预期难看，或者和图片不一样",
    "good_grip": "鞋底抓地好、不打滑",
    "slippery": "鞋底打滑",
}


def main():
    judgments = json.load(open(os.path.join(ROOT_DIR, "eval", "results", "judgments.json")))
    reviews = {r["review_id"]: r for r in json.load(open(os.path.join(ROOT_DIR, "data", "shoes", "reviews.json")))}
    highlights = json.load(open(os.path.join(ROOT_DIR, "data", "shoes", "highlights.json")))

    # key: "<model>|stance|<stance>|<review_id>"
    pairs = {"yes": [], "no": []}
    for key, verdict in sorted(judgments.items()):
        model, kind, stance, rid = key.split("|")
        if model == JUDGE.model and kind == "stance":
            pairs["yes" if verdict else "no"].append((stance, rid))
    yes_rate = len(pairs["yes"]) / (len(pairs["yes"]) + len(pairs["no"]))

    rng = random.Random(SEED)
    sample = rng.sample(pairs["yes"], PER_VERDICT) + rng.sample(pairs["no"], PER_VERDICT)
    rng.shuffle(sample)

    rows, hidden = [], []
    for i, (stance, rid) in enumerate(sample, start=1):
        r = reviews[rid]
        checked = highlights[r["asin"]]["checked"]
        earlier = judgments.get(f"{EARLIER_JUDGE}|stance|{stance}|{rid}")
        rows.append({
            "pair": i,
            "review_id": rid,
            "stars": r["rating"],
            "review": f"{r['title']}. {r['text']}",
            "point_en": f"The review says that {STANCES[stance][1]}.",
            "point_zh": f"评论里说了：{STATEMENT_ZH[stance]}",
            "label": "",
        })
        hidden.append({
            "pair": i,
            "review_id": rid,
            "stance": stance,
            "judge": judgments[f"{JUDGE.model}|stance|{stance}|{rid}"],
            "generator": rid in checked[stance] if stance in checked else None,
            "earlier_judge": earlier,
        })

    path = os.path.join(ROOT_DIR, "eval", "annotation", "judge_labels.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(ROOT_DIR, "eval", "results", "judge_sample.json"), "w") as f:
        json.dump({"judge_model": JUDGE.model, "earlier_judge": EARLIER_JUDGE,
                   "judge_yes_rate": round(yes_rate, 4), "per_verdict": PER_VERDICT,
                   "pairs": hidden}, f, indent=1)
    print(f"{len(rows)} pairs -> {path} (judge yes-rate over all highlight judgments: {yes_rate:.3f})")


if __name__ == "__main__":
    main()
