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

# Collection names (Legacy - 兼容旧代码)
COLLECTIONS = {
    "visual": "product_visual_desc",
    "reviews": "reviews_chunks",
    "knowledge": "material_knowledge",
    "sizing": "sizing_guide",
}

# New Qdrant-First Collections
QDRANT_COLLECTIONS = {
    "products": "products_v2",           # 商品语义搜索
    "reviews": "reviews_v2",             # 评价语义搜索
    "knowledge": "knowledge_v2",         # 专业知识
    "visual_semantic": "visual_semantic_v2",  # 视觉语义
}

VECTOR_SIZE = int(os.getenv("VECTOR_SIZE", "1024"))

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
