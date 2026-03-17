"""
config/settings.py
Central configuration — put your API keys here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Qdrant ──────────────────────────────────────────────────────────────────
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None

# Qdrant Collections
QDRANT_COLLECTIONS = {
    "products": "products",
    "reviews": "reviews",
    "knowledge": "knowledge",
    "visual_semantic": "visual_semantic",
}

VECTOR_SIZE = int(os.getenv("VECTOR_SIZE", "384"))

# ── Model Provider (OpenAI-compatible) ──────────────────────────────────────
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

TEXT_MODEL = os.getenv("TEXT_MODEL", "qwen3.5-35b-a3b")
VISION_MODEL = os.getenv("VISION_MODEL", "qwen3.5-35b-a3b")

# Embedding model (DashScope OpenAI-compatible endpoint)
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-v4")

# ── Retrieval ────────────────────────────────────────────────────────────────
TOP_K = 5  # results per Qdrant query
MAX_CONTEXT_TOKENS = 2000
