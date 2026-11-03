"""scripts/build_highlights.py

Precompute the spoken review highlights for every product (feature 1).

Tagging 30 reviews takes three model calls, too slow to run while a blind
shopper waits on a product page, so highlights are built offline, the way a
retailer would refresh them when new reviews arrive. Products are processed
CONCURRENCY at a time. Each result is written to data/shoes/highlights.json
as soon as it is done, and a rerun skips products already there, so an
interrupted run picks up where it stopped. Delete the file to rebuild
everything, e.g. after changing LLM_MODEL.

At the end the script prints wall-clock time and token usage, from which the
cost follows from the provider's price list.

Usage:
    python scripts/build_highlights.py
"""

import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.review_insights import tag_reviews
from config.settings import LLM, ROOT_DIR
from core.llm import usage_summary

SHOES = os.path.join(ROOT_DIR, "data", "shoes")
OUT = os.path.join(SHOES, "highlights.json")
CONCURRENCY = 8


def main():
    products = json.load(open(os.path.join(SHOES, "products.json")))
    reviews = defaultdict(list)
    for r in json.load(open(os.path.join(SHOES, "reviews.json"))):
        reviews[r["asin"]].append(r)

    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    todo = [p for p in products if p["asin"] not in done]
    print(f"{len(done)} done, {len(todo)} to go (model: {LLM.model})")

    start = time.time()
    with ThreadPoolExecutor(CONCURRENCY) as pool:
        futures = {pool.submit(tag_reviews, p, reviews[p["asin"]]): p["asin"] for p in todo}
        for i, future in enumerate(as_completed(futures), start=1):
            done[futures[future]] = future.result()
            with open(OUT + ".tmp", "w") as f:
                json.dump(done, f, ensure_ascii=False, indent=1)
            os.replace(OUT + ".tmp", OUT)
            print(f"[{i}/{len(todo)}] {futures[future]}  {time.time() - start:.0f}s")

    print(f"\nWall clock: {time.time() - start:.0f}s")
    print("Token usage:", json.dumps(usage_summary(), indent=1))


if __name__ == "__main__":
    main()
