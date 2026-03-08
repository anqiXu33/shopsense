"""
config/settings.py
Central configuration — put your API keys here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Qdrant ──────────────────────────────────────────────────────────────────
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# Collection names
COLLECTIONS = {
    "visual": "product_visual_desc",
    "reviews": "reviews_chunks",
    "knowledge": "material_knowledge",
    "sizing": "sizing_guide",
}

VECTOR_SIZE = 384  # matches all-MiniLM-L6-v2

# ── HuggingFace ──────────────────────────────────────────────────────────────
HF_API_KEY = os.getenv("HF_API_KEY")


QWEN_MODEL = "Qwen/Qwen2.5-VL-72B-Instruct"

# Embedding model (runs locally, no API cost)
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# ── Retrieval ────────────────────────────────────────────────────────────────
TOP_K = 5  # results per Qdrant query
MAX_CONTEXT_TOKENS = 2000

# Token budget per intent type
# Format: {intent: {source: fraction_of_remaining_budget}}
TOKEN_BUDGETS = {
    "warmth_inquiry": {"knowledge": 0.50, "reviews": 0.40, "sizing": 0.10},
    "material_sensitivity": {"knowledge": 0.55, "reviews": 0.40, "sizing": 0.05},
    "size_fitting": {"knowledge": 0.10, "reviews": 0.40, "sizing": 0.50},
    "appearance_inquiry": {"knowledge": 0.00, "reviews": 0.30, "sizing": 0.00},
    "review_summary": {"knowledge": 0.00, "reviews": 1.00, "sizing": 0.00},
    "usage_context": {"knowledge": 0.35, "reviews": 0.55, "sizing": 0.10},
    "default": {"knowledge": 0.35, "reviews": 0.45, "sizing": 0.20},
}
