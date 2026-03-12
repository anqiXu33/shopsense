from __future__ import annotations
"""
agent/intent.py
Classifies user query into intent + extracts entities.
Uses keyword-based rules (reliable, fast, no API cost).
Can be swapped for an LLM classifier later.
"""

import re

INTENT_PATTERNS = {
    "warmth_inquiry": [
        r"\b(warm|cold|freezing|temperature|degree|celsius|winter|insulate|heat)\b"
    ],
    "material_sensitivity": [
        r"\b(sensitive|itch|allerg|skin|scratch|rash|eczema|irritat|soft|rough|texture|fabric|feel)\b"
    ],
    "size_fitting": [
        r"\b(size|fit|cm|kg|tall|height|weight|small|large|tight|loose|runs|measurement)\b"
    ],
    "appearance_inquiry": [
        r"\b(color|colour|look|style|design|pattern|shape|pocket|detail|appear|what does)\b"
    ],
    "review_summary": [
        r"\b(review|complaint|problem|issue|people say|buyers|customers|rating|opinion|feedback)\b"
    ],
    "usage_context": [
        r"\b(wear|use|occasion|suitable|appropriate|office|outdoor|formal|casual|gym|travel)\b"
    ],
}

def classify_intent(query: str) -> dict:
    """
    Returns:
        {
            "primary_intent": str,
            "all_intents": list[str],
            "entities": {
                "height": int | None,
                "weight": int | None,
                "temperature": int | None,
                "skin_condition": str | None,
            }
        }
    """
    query_lower = query.lower()
    matched_intents = []

    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, query_lower):
                matched_intents.append(intent)
                break

    if not matched_intents:
        matched_intents = ["appearance_inquiry"]  # safe default

    entities = _extract_entities(query_lower)

    # If height/weight mentioned, bump size_fitting to top
    if entities.get("height") or entities.get("weight"):
        if "size_fitting" not in matched_intents:
            matched_intents.insert(0, "size_fitting")
        primary = "size_fitting"
    else:
        primary = matched_intents[0]

    return {
        "primary_intent": primary,
        "all_intents": matched_intents,
        "entities": entities,
    }


def _extract_entities(query: str) -> dict:
    entities = {
        "height": None,
        "weight": None,
        "temperature": None,
        "skin_condition": None,
    }

    # Height: "170cm", "170 cm", "5'7"
    m = re.search(r"(\d{3})\s*cm", query)
    if m:
        entities["height"] = int(m.group(1))

    # Weight: "55kg", "55 kg"
    m = re.search(r"(\d{2,3})\s*kg", query)
    if m:
        entities["weight"] = int(m.group(1))

    # Temperature: "-10", "-10 degrees", "minus 10"
    m = re.search(r"(-\d+|minus\s*\d+)\s*(degree|celsius|°|c\b)", query)
    if m:
        val = m.group(1).replace("minus", "-").replace(" ", "")
        entities["temperature"] = int(val)

    # Skin condition keywords
    if re.search(r"\b(sensitive|eczema|allerg|rash)\b", query):
        entities["skin_condition"] = "sensitive"

    return entities
