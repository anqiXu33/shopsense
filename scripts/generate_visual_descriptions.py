"""scripts/generate_visual_descriptions.py

Describe what each shoe looks like, from its main product photo, for a
blind shopper. The configured LLM_MODEL must accept image input.

Reviews say how a shoe fits and feels but rarely what it looks like, and the
photo is the one part of a listing a screen reader cannot read. Each
description is written in English and Chinese and stored in
data/shoes/visual.json; scripts/ingest_all.py loads it into the product
payload (shown on the product page).

Like the highlights, descriptions are built offline and the script resumes:
products already in visual.json are skipped. Delete the file to rebuild.

Usage:
    python scripts/generate_visual_descriptions.py
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import LLM, ROOT_DIR
from core.llm import chat_json, object_schema, usage_summary

SHOES = os.path.join(ROOT_DIR, "data", "shoes")
OUT = os.path.join(SHOES, "visual.json")
CONCURRENCY = 8

PROMPT = (
    "This is the main listing photo for: {name}\n\n"
    "Describe what the shoe looks like for a blind shopper, in 2 or 3 short "
    "sentences: the kind of shoe, its colours, what the upper looks made of, "
    "how it fastens, and what the sole looks like. Describe only what is "
    "visible in the photo; do not repeat marketing claims or guess at comfort "
    "or fit. If the photo shows a pair or several angles, describe one shoe. "
    "Write the description in English in the \"en\" field and the same "
    "description in Chinese in the \"zh\" field; keep each field in its own "
    "language only."
)


def describe(product: dict) -> dict:
    out = chat_json(
        [{"role": "user", "content": [
            {"type": "text", "text": PROMPT.format(name=product["name"])},
            # "low" detail (512 px) is plenty for colour and shape, at a
            # fraction of the tokens of the full-resolution image.
            {"type": "image_url", "image_url": {"url": product["image_url"], "detail": "low"}},
        ]}],
        schema=object_schema({"en": {"type": "string"}, "zh": {"type": "string"}}),
    )
    return {"en": out["en"].strip(), "zh": out["zh"].strip(), "image_url": product["image_url"]}


def main():
    products = json.load(open(os.path.join(SHOES, "products.json")))
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    todo = [p for p in products if p["asin"] not in done]
    print(f"{len(done)} done, {len(todo)} to go (model: {LLM.model})")

    start = time.time()
    with ThreadPoolExecutor(CONCURRENCY) as pool:
        futures = {pool.submit(describe, p): p["asin"] for p in todo}
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
