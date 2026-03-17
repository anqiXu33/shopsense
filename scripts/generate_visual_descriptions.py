"""scripts/generate_visual_descriptions.py

Use Groq's Llama vision model to analyze actual product images and generate
accurate accessibility descriptions. Overwrites data/visual_semantic.json.

Usage:
    python scripts/generate_visual_descriptions.py
"""

import json
import os
import sys
import time

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

PRODUCTS = [
    {"asin": "P001", "name": "Alpine Duck Down Jacket",    "brand": "NorthPeak",    "color": "navy blue",    "material": "duck down + polyester shell", "image_url": "https://media.maisonkitsune.com/media/catalog/product/cache/5b6799a1e14ed1d66eedf309ab07601e/p/m/pm02221wq4064-0413_1_1.jpg"},
    {"asin": "P002", "name": "Waterproof Trench Coat",      "brand": "UrbanShell",   "color": "khaki beige",  "material": "polyester + waterproof membrane", "image_url": "https://images.unsplash.com/photo-1539533018447-63fcce2678e3?auto=format&fit=crop&w=800&q=80"},
    {"asin": "P003", "name": "Merino Wool Turtleneck",      "brand": "WoolCraft",    "color": "ivory white",  "material": "100% merino wool", "image_url": "https://ecdn.speedsize.com/90526ea8-ead7-46cf-ba09-f3be94be750a/www.boggi.com/dw/image/v2/BBBS_PRD/on/demandware.static/-/Sites-BoggiCatalog/default/dw0741ab18/images/hi-res/BO25A076004_1.jpeg"},
    {"asin": "P004", "name": "Cashmere Blend Scarf",        "brand": "LuxeKnit",     "color": "camel brown",  "material": "cashmere + silk blend", "image_url": "https://images.unsplash.com/photo-1520903920243-00d872a2d1c9?auto=format&fit=crop&w=800&q=80"},
    {"asin": "P005", "name": "Fleece Zip-Up Hoodie",        "brand": "CozyLayer",    "color": "heather grey", "material": "recycled polyester fleece", "image_url": "https://cdn-images.farfetch-contents.com/32/30/23/76/32302376_62445519_2048.jpg"},
    {"asin": "P006", "name": "Cotton Oxford Shirt",         "brand": "ClassicFit",   "color": "white",        "material": "100% cotton", "image_url": "https://ecdn.speedsize.com/90526ea8-ead7-46cf-ba09-f3be94be750a/www.boggi.com/dw/image/v2/BBBS_PRD/on/demandware.static/-/Sites-BoggiCatalog/default/dw330844f2/images/hi-res/BO25A056901_5.jpeg"},
    {"asin": "P007", "name": "Thermal Base Layer Set",      "brand": "ThermoCore",   "color": "charcoal grey","material": "merino wool blend", "image_url": "https://media.revolutionrace.com/api/media/image/b6f878b2-d01e-4ce2-83e0-cc840f0edd04/image.jpg?width=1200"},
    {"asin": "P008", "name": "Windproof Softshell Jacket",  "brand": "TrailBlaze",   "color": "forest green", "material": "softshell polyester", "image_url": "https://media.revolutionrace.com/api/media/image/db6235c8-5134-4fad-9993-934927801591/image.jpg?width=1200"},
    {"asin": "P009", "name": "Linen Summer Shirt",          "brand": "BreezeWear",   "color": "sky blue",     "material": "100% Belgian linen", "image_url": "https://frame-store.com/cdn/shop/files/MS26WSH003_BLST-MS26WPA003_DKNV_00942.jpg?v=1767730004&width=1280"},
    {"asin": "P010", "name": "Quilted Puffer Vest",         "brand": "AlpineStyle",  "color": "dark blue",    "material": "synthetic fill + nylon shell", "image_url": "https://aurelien-online.com/cdn/shop/files/aurelien_body_warmer_jacket_cashmere_blend_navy1_a51648b4-10e0-45fe-98aa-2bc09d86260f.jpg?v=1759496270&width=1400"},
    {"asin": "P011", "name": "Stretch Denim Jeans",         "brand": "DenimLab",     "color": "indigo blue",  "material": "cotton + elastane", "image_url": "https://images.unsplash.com/photo-1542272604-787c3835535d?auto=format&fit=crop&w=800&q=80"},
    {"asin": "P012", "name": "Lounge Set",                  "brand": "EcoComfort",   "color": "sage green",   "material": "bamboo viscose", "image_url": "https://image01.bonprix.ch/assets/880x1232/2x/1763992631/25163184-iScxMZl2.webp"},
    {"asin": "P013", "name": "Merino Running Socks",        "brand": "SockTech",     "color": "white/grey",   "material": "merino wool blend", "image_url": "https://images.unsplash.com/photo-1586350977771-b3b0abd50c82?auto=format&fit=crop&w=800&q=80"},
    {"asin": "P014", "name": "Corduroy Overshirt",          "brand": "LayerUp",      "color": "rust orange",  "material": "100% cotton corduroy", "image_url": "https://www.bfgcdn.com/1500_1500_90/033-2664-0311/passenger-backcountry-cord-shirt-hemd.jpg"},
    {"asin": "P015", "name": "Long Down Blanket Coat",      "brand": "CoatCo",       "color": "oyster white",  "material": "goose down + ripstop nylon", "image_url": "https://ch.oneill.com/cdn/shop/files/1500136_17525_01_MODEL.jpg?v=1749222969&width=2000"},
]

VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://api.groq.com/openai/v1")
API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("HF_API_KEY")


def describe_image(product: dict) -> str:
    """Call Groq vision model to describe the actual product image."""
    prompt = (
        f"This is a product listing image for '{product['name']}' by {product['brand']}.\n"
        f"Listed color: {product['color']} | Material: {product['material']}\n\n"
        f"Your task: describe ONLY the '{product['name']}' garment for a visually impaired shopper.\n"
        "If a model is wearing the item, focus exclusively on the featured garment — ignore the model's body, "
        "face, hair, skin, and any other clothing or accessories they are wearing. "
        "If the image shows multiple garments, describe only the one matching the product name above.\n\n"
        "Cover: actual color and shade, garment type, silhouette/shape, visible textures, "
        "closures (zips/buttons), pockets, collar/neckline, and any notable design details. "
        "If the image color differs from the listed color, describe what you actually see. "
        "Write 3-5 sentences, no bullet points. Do not mention the model or other people."
    )

    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": product["image_url"]}},
                    ],
                }
            ],
            "max_tokens": 300,
            "temperature": 0.3,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def main():
    print("=" * 60)
    print("ShopSense — Vision Description Generator")
    print(f"Model: {VISION_MODEL}")
    print("=" * 60)

    output = []
    failed = []

    for i, product in enumerate(PRODUCTS, 1):
        print(f"\n[{i:02d}/15] {product['asin']}: {product['name']}")
        print(f"         Image: {product['image_url'][:60]}...")

        try:
            description = describe_image(product)
            print(f"         ✓ {description[:80]}...")
            output.append({
                "asin": product["asin"],
                "image_type": "product_main",
                "text": description,
            })
        except Exception as e:
            print(f"         ✗ Failed: {e}")
            failed.append(product["asin"])
            # Keep existing description as fallback if available
            output.append({
                "asin": product["asin"],
                "image_type": "product_main",
                "text": f"[Vision unavailable] {product['name']} in {product['color']}.",
            })

        # Rate limit: Groq free tier allows ~30 req/min
        if i < len(PRODUCTS):
            time.sleep(2)

    out_path = os.path.join(DATA_DIR, "visual_semantic.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"✓ Saved {len(output)} descriptions → {out_path}")
    if failed:
        print(f"✗ Failed ASINs: {failed}")
    print("\nNext step: python scripts/ingest_all.py  (re-uploads to Qdrant)")
    print("=" * 60)


if __name__ == "__main__":
    main()
