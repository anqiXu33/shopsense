"""
agent/page.py

Answer a question about a product page that the browser extension scraped.

Nothing about that product is in Qdrant — it is a live listing on somebody
else's site — so every statement here has to come from the page itself: the
seller's own title and copy on one side, the reviews visible on the page on the
other. That is exactly the comparison the conflict detector is built for, so
the extension gets the same "the listing says X but buyers report Y" warning as
the demo app, with no stored data and no vector search.

Entry point: answer_from_page(payload) -> dict
"""

import asyncio
import os

import requests as req_lib

from agent.react import VOICE_RULES, _detect_conflicts

# The page can hand us an unbounded amount of text; keep the prompt sane.
MAX_REVIEWS = 12
MAX_REVIEW_CHARS = 400
MAX_DESCRIPTION_CHARS = 1200


def build_page_product(payload) -> dict:
    """Shape the scraped fields like a stored product so shared code fits them."""
    bullets = [b.strip() for b in (getattr(payload, "bullets", None) or []) if b and b.strip()]
    description = (payload.description or "").strip()
    if not description and bullets:
        description = ". ".join(bullets)
    return {
        "name": (payload.title or "").strip(),
        "brand": (payload.brand or "").strip(),
        "price": (payload.price or "").strip(),
        "description": description[:MAX_DESCRIPTION_CHARS],
        "attributes": {},
    }


def build_page_reviews(payload) -> list:
    """
    Reviews taken straight off the page.

    relevance_score is 1.0 because nothing was retrieved or ranked: these are
    the reviews the shopper can already see, not search results competing for a
    place in the context.
    """
    items = []
    for text in (payload.reviews or [])[:MAX_REVIEWS]:
        text = (text or "").strip()
        if text:
            items.append({"text": text[:MAX_REVIEW_CHARS], "relevance_score": 1.0})
    return items


def build_prompt(product: dict, reviews: list, conflict: dict) -> str:
    """The whole world the model is allowed to draw on, and how to say it."""
    listing = [f"Title: {product['name'] or 'not stated on the page'}"]
    if product["brand"]:
        listing.append(f"Brand: {product['brand']}")
    if product["price"]:
        listing.append(f"Price as shown: {product['price']}")
    if product["description"]:
        listing.append(f"Description: {product['description']}")

    review_block = (
        "\n".join('- "%s"' % r["text"] for r in reviews)
        if reviews else "None were visible on this page."
    )
    conflict_block = (
        conflict["details"] if conflict["has_conflict"]
        else "No contradiction found between the listing and the reviews on this page."
    )

    return (
        "You are ShopSense, a voice-first shopping assistant for a blind shopper "
        "who is on this product page right now.\n"
        "Everything you know is below, read off the page itself. Never add product "
        "knowledge that is not in it, and never describe what the item looks like "
        "beyond what the text says.\n\n"

        "## Listing (what the seller wrote)\n" + "\n".join(listing) + "\n\n"
        f"## Reviews visible on the page\n{review_block}\n\n"
        f"## Conflict check\n{conflict_block}\n\n"

        + VOICE_RULES +

        "## Conflict Handling\n"
        "If the conflict check above found something, lead with both sides and name "
        "them: the listing claimed one thing, buyers report another. Say which side "
        "to trust for this kind of claim — the listing is authoritative for materials "
        "and measurements, buyers are authoritative for fit, durability and how it "
        "feels on the skin — then give one practical tip.\n"
        "If it found nothing, do not invent a warning."
    )


def build_fallback_answer(product: dict, reviews: list, conflict: dict) -> str:
    """
    What to say when no language model is reachable.

    Still worth more than the extension's own offline summary, because the
    conflict check has already run over the real page content.
    """
    def quote(text):
        # trailing punctuation inside a quote makes the sentence stutter aloud
        return text.strip().rstrip(".,;: ")

    parts = []
    if product["name"]:
        parts.append(f"This listing is for {product['name']}.")
    if conflict["has_conflict"]:
        first = conflict["conflicts"][0]
        parts.append(
            f"Take care on {first['topic']}. The {first['source'].replace('the ', '')} "
            f"says \"{quote(first['claim'])}\", "
            f"but a buyer reports \"{quote(first['counter'])}\"."
        )
    elif reviews:
        parts.append(
            "Nothing in the reviews on this page contradicts the seller's description."
        )
    else:
        parts.append(
            "No reviews were visible on this page, so the description could not be checked."
        )
    parts.append(
        "This is a direct reading of the page, because the assistant could not "
        "reach its language model."
    )
    return " ".join(parts)


async def answer_from_page(payload) -> dict:
    """Compare the listing with the page's own reviews and answer out loud."""
    product = build_page_product(payload)
    reviews = build_page_reviews(payload)
    conflict = _detect_conflicts([], reviews, product)

    question = (payload.question or "").strip() or (
        "Describe this product and flag anything that does not add up."
    )

    base_url = os.getenv("DASHSCOPE_BASE_URL", "https://api.groq.com/openai/v1")
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("HF_API_KEY")
    model = os.getenv("TEXT_MODEL", "llama-3.3-70b-versatile")

    answer, source = "", "page_only"
    if api_key:
        try:
            resp = await asyncio.to_thread(
                req_lib.post,
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": build_prompt(product, reviews, conflict)},
                        {"role": "user", "content": question},
                    ],
                    "max_tokens": 220,
                    "temperature": 0.3,
                },
                timeout=25,
            )
            resp.raise_for_status()
            answer = (resp.json()["choices"][0]["message"].get("content") or "").strip()
            if answer:
                source = "page_llm"
        except Exception:
            answer = ""

    if not answer:
        answer = build_fallback_answer(product, reviews, conflict)

    return {
        "answer": answer,
        "conflict_detection": conflict,
        "source": source,
        "reviews_read": len(reviews),
    }
