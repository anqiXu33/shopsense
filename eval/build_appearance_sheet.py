"""eval/build_appearance_sheet.py

Step 1 of the appearance-description check: sample 30 products with a fixed
seed and export their AI-written descriptions for a human to compare with
the photo.

Outputs:
    eval/annotation/appearance_labels.csv   the sheet to label (UTF-8 with BOM)
    eval/annotation/appearance_review.html  the same 30 items with their photos,
                                            to look at while labelling

Each item is judged on five things the description is asked to cover (kind
of shoe, colours, upper, fastening, sole), plus whether it invents anything
that is not in the photo and whether the Chinese text says the same as the
English. The rules are in eval/annotation/README.md; scores come from
eval/appearance_metrics.py.

Rerunning overwrites both files, so do not rerun after you start labelling.

Usage:
    python eval/build_appearance_sheet.py
"""

import csv
import html
import json
import os
import random
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import ROOT_DIR

N_ITEMS = 30
SEED = 2026
ANNOTATION = os.path.join(ROOT_DIR, "eval", "annotation")
LABEL_COLUMNS = ["kind_ok", "colour_ok", "upper_ok", "fastening_ok", "sole_ok", "invented_detail", "zh_matches_en"]


def main():
    products = json.load(open(os.path.join(ROOT_DIR, "data", "shoes", "products.json")))
    visual = json.load(open(os.path.join(ROOT_DIR, "data", "shoes", "visual.json")))
    sample = random.Random(SEED).sample(sorted(products, key=lambda p: p["asin"]), N_ITEMS)

    rows = [
        {
            "item": i,
            "asin": p["asin"],
            "product": p["name"],
            "image_url": visual[p["asin"]]["image_url"],
            "description_en": visual[p["asin"]]["en"],
            "description_zh": visual[p["asin"]]["zh"],
            **{c: "" for c in LABEL_COLUMNS},
            "notes": "",
        }
        for i, p in enumerate(sample, start=1)
    ]

    csv_path = os.path.join(ANNOTATION, "appearance_labels.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    cards = "\n".join(
        f"""<article>
  <h2>#{r['item']} · {html.escape(r['product'])}</h2>
  <p class="asin">{r['asin']}</p>
  <img src="{html.escape(r['image_url'])}" alt="Photo #{r['item']}: {html.escape(r['product'])}" loading="lazy">
  <p lang="en">{html.escape(r['description_en'])}</p>
  <p lang="zh-CN">{html.escape(r['description_zh'])}</p>
</article>"""
        for r in rows
    )
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Appearance check</title>
<style>
  :root {{ --bg: #fff; --text: #111827; --muted: #4b5563; --border: #d1d5db; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg: #111827; --text: #f3f4f6; --muted: #9ca3af; --border: #374151; }} }}
  body {{ margin: 0; padding: 1.5rem 1rem; background: var(--bg); color: var(--text);
         font: 16px/1.6 system-ui, sans-serif; }}
  main {{ max-width: 46rem; margin: 0 auto; }}
  article {{ border-top: 1px solid var(--border); padding: 1.5rem 0; }}
  h2 {{ font-size: 1.1rem; margin: 0; }}
  .asin {{ color: var(--muted); margin: 0.25rem 0 0.75rem; font-size: 0.875rem; }}
  img {{ max-width: 100%; max-height: 22rem; background: #fff; display: block; }}
</style>
</head>
<body>
<main>
<h1>外观描述核对：{N_ITEMS} 张图</h1>
<p>对照每张图片和下面的描述，在 <code>appearance_labels.csv</code> 里按同样的编号填写。规则见 <code>README.md</code>。</p>
{cards}
</main>
</body>
</html>
"""
    with open(os.path.join(ANNOTATION, "appearance_review.html"), "w") as f:
        f.write(page)
    print(f"{len(rows)} items -> {csv_path} and appearance_review.html")


if __name__ == "__main__":
    main()
