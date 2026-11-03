"""scripts/build_dataset.py

Build the shoe subset of Amazon Reviews 2023 (McAuley Lab) that the demo
store runs on.

Source: https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023
        category "Clothing_Shoes_and_Jewelry" (raw review + meta files)
Paper:  Hou et al., "Bridging Language and Items for Retrieval and
        Recommendation", arXiv:2403.03952, 2024.
Use:    research / non-commercial demonstration only.

The two category files are 18 GB (meta) and 28 GB (reviews), and the review
file is ordered by user, not by product. Instead of downloading everything,
the script fetches a fixed-size prefix of each file with an HTTP Range
request. Products are picked from the meta prefix (shoes with at least
MIN_RATINGS ratings), and their reviews are collected from the review prefix.
Popular products are spread evenly through the review file, so a 1.5 GB
prefix already holds dozens of reviews for each of them.

Everything is deterministic: the same prefix sizes and constants always give
the same products and reviews. The prefixes are kept in data/raw/ so a rerun
does not download them again.

Output:
    data/shoes/products.json
    data/shoes/reviews.json

Usage:
    python scripts/build_dataset.py
"""

import html
import json
import os
import re
import sys

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import ROOT_DIR

HF_BASE = "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw"
META_URL = f"{HF_BASE}/meta_categories/meta_Clothing_Shoes_and_Jewelry.jsonl"
REVIEW_URL = f"{HF_BASE}/review_categories/Clothing_Shoes_and_Jewelry.jsonl"

META_BYTES = 600_000_000
REVIEW_BYTES = 1_500_000_000

MIN_RATINGS = 1000          # only well-reviewed shoes
N_PRODUCTS = 300
MIN_REVIEWS = 20            # a product needs at least this many usable reviews
MAX_REVIEWS = 30            # and keeps at most this many
MIN_REVIEW_CHARS = 80       # "Great shoes!" carries nothing to retrieve
MAX_REVIEW_CHARS = 1200

RAW_DIR = os.path.join(ROOT_DIR, "data", "raw")
OUT_DIR = os.path.join(ROOT_DIR, "data", "shoes")


def download_prefix(url: str, n_bytes: int, dest: str) -> None:
    if os.path.exists(dest) and os.path.getsize(dest) == n_bytes:
        print(f"  cached: {dest}")
        return
    print(f"  downloading first {n_bytes / 1e9:.1f} GB of {url.rsplit('/', 1)[-1]}")
    with requests.get(url, headers={"Range": f"bytes=0-{n_bytes - 1}"}, stream=True, timeout=60) as r:
        r.raise_for_status()
        done = 0
        with open(dest + ".part", "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                done += len(chunk)
                if done % (100 << 20) < (1 << 20):
                    print(f"    {done / 1e9:.2f} GB")
    if os.path.getsize(dest + ".part") != n_bytes:
        raise RuntimeError(f"Expected {n_bytes} bytes, got {os.path.getsize(dest + '.part')}")
    os.replace(dest + ".part", dest)


def complete_lines(path: str):
    """Yield parsed JSON lines, skipping the last one the byte cut truncated."""
    with open(path, "rb") as f:
        for raw in f:
            if not raw.endswith(b"\n"):
                return
            yield json.loads(raw)


_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def clean(text: str) -> str:
    return _SPACE.sub(" ", _TAG.sub(" ", html.unescape(text))).strip()


def pick_candidates(meta_path: str) -> dict:
    candidates = {}
    for item in complete_lines(meta_path):
        cats = item["categories"]
        if len(cats) < 4 or cats[2] != "Shoes" or cats[1] not in ("Women", "Men"):
            continue
        if (item["rating_number"] or 0) < MIN_RATINGS or not item["images"]:
            continue
        candidates[item["parent_asin"]] = item
    return candidates


def collect_reviews(review_path: str, candidates: dict) -> dict:
    reviews = {asin: [] for asin in candidates}
    for r in complete_lines(review_path):
        bucket = reviews.get(r["parent_asin"])
        if bucket is None or len(bucket) >= MAX_REVIEWS:
            continue
        text = clean(r["text"])
        if len(text) < MIN_REVIEW_CHARS:
            continue
        bucket.append({
            "title": clean(r["title"]),
            "text": text[:MAX_REVIEW_CHARS],
            "rating": int(r["rating"]),
            "helpful_vote": r["helpful_vote"],
            "verified_purchase": r["verified_purchase"],
            "timestamp": r["timestamp"],
        })
    return reviews


def to_product(item: dict, n_reviews: int) -> dict:
    cats = item["categories"]
    image = item["images"][0]
    return {
        "asin": item["parent_asin"],
        "name": clean(item["title"]),
        "brand": item["store"] or "",
        "gender": cats[1],
        "category": cats[-1],
        "category_path": cats[3:],
        "price": item["price"],
        "rating": item["average_rating"],
        "review_count": item["rating_number"],
        "n_reviews": n_reviews,
        "image_url": image.get("hi_res") or image["large"],
        "features": [clean(f) for f in item["features"]][:6],
        "description": clean(" ".join(item["description"]))[:800],
    }


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    meta_path = os.path.join(RAW_DIR, "meta_Clothing_Shoes_and_Jewelry.prefix.jsonl")
    review_path = os.path.join(RAW_DIR, "Clothing_Shoes_and_Jewelry.prefix.jsonl")

    print("[1/4] Downloading file prefixes")
    download_prefix(META_URL, META_BYTES, meta_path)
    download_prefix(REVIEW_URL, REVIEW_BYTES, review_path)

    print("[2/4] Picking shoe candidates")
    candidates = pick_candidates(meta_path)
    print(f"  {len(candidates)} shoes with >= {MIN_RATINGS} ratings")

    print("[3/4] Collecting reviews")
    reviews = collect_reviews(review_path, candidates)
    usable = [a for a, rs in reviews.items() if len(rs) >= MIN_REVIEWS]
    print(f"  {len(usable)} shoes with >= {MIN_REVIEWS} usable reviews")

    # Most-reviewed first, so the subset is the shoes with the richest
    # review sets; ASIN breaks ties so the order never depends on dict order.
    usable.sort(key=lambda a: (-len(reviews[a]), a))
    chosen = usable[:N_PRODUCTS]
    if len(chosen) < N_PRODUCTS:
        raise RuntimeError(f"Only {len(chosen)} products qualify; raise META_BYTES / REVIEW_BYTES")
    chosen.sort()

    print("[4/4] Writing output")
    products = [to_product(candidates[a], len(reviews[a])) for a in chosen]
    review_rows = []
    for a in chosen:
        for i, r in enumerate(reviews[a], start=1):
            review_rows.append({"review_id": f"{a}-{i:02d}", "asin": a, **r})

    with open(os.path.join(OUT_DIR, "products.json"), "w") as f:
        json.dump(products, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT_DIR, "reviews.json"), "w") as f:
        json.dump(review_rows, f, ensure_ascii=False, indent=1)
    print(f"  {len(products)} products, {len(review_rows)} reviews -> {OUT_DIR}")


if __name__ == "__main__":
    main()
