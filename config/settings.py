"""
config/settings.py
Central configuration — values come from .env (see .env.example).
"""

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Qdrant ──────────────────────────────────────────────────────────────────
# Two ways to run Qdrant, picked by which variable is set:
#   QDRANT_PATH — embedded local mode: a folder on disk, no server process.
#                 Only one process can open the folder at a time, so stop the
#                 backend before running the ingest or eval scripts.
#   QDRANT_URL  — a Qdrant server (docker, binary or Qdrant Cloud).
QDRANT_PATH = os.getenv("QDRANT_PATH") or None
QDRANT_URL = os.getenv("QDRANT_URL") or None
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None

# Qdrant Collections
QDRANT_COLLECTIONS = {
    "products": "products",
    "reviews": "reviews",
    "knowledge": "knowledge",
    "visual_semantic": "visual_semantic",
}


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """One shared client per process (local mode allows only one)."""
    if QDRANT_PATH:
        path = QDRANT_PATH if os.path.isabs(QDRANT_PATH) else os.path.join(ROOT_DIR, QDRANT_PATH)
        return QdrantClient(path=path)
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


# ── Embeddings ──────────────────────────────────────────────────────────────
# Multilingual, because shoppers ask in Chinese or English while the Amazon
# reviews are English. E5 models expect "query: " / "passage: " prefixes,
# which core/embeddings.py adds.
EMBED_MODEL = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-small")
VECTOR_SIZE = int(os.getenv("VECTOR_SIZE", "384"))

# ── Language model (any OpenAI-compatible chat endpoint) ────────────────────
# Switching models only means editing .env: OpenAI, DeepSeek, a local Ollama
# server … all speak the same /chat/completions protocol.
#   LLM_BASE_URL    e.g. https://api.openai.com/v1, https://api.deepseek.com/v1,
#                   http://127.0.0.1:11434/v1 (Ollama)
#   LLM_API_KEY     the provider's key (any non-empty string for Ollama)
#   LLM_MODEL       e.g. gpt-6-luna, deepseek-v4-flash, qwen3.5:9b
#   LLM_EXTRA_BODY  optional JSON merged into every request, for parameters
#                   only some models take, e.g. {"reasoning_effort": "low"}
#                   for OpenAI reasoning models or {"temperature": 0} for Ollama.
# The model must accept image input for scripts/generate_visual_descriptions.py.
#
# The eval judge (eval/check_numbers.py) has its own JUDGE_* settings, each
# defaulting to the LLM_* value. Pin the judge when comparing models, so a
# change in the score comes from the model under test, not from the judge.


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str = field(repr=False)  # never printed in logs or tracebacks
    model: str
    extra_body: dict


def _llm_config(prefix: str, default: LLMConfig | None = None) -> LLMConfig:
    def get(name, fallback):
        return os.getenv(f"{prefix}_{name}") or fallback
    extra = get("EXTRA_BODY", None)
    return LLMConfig(
        base_url=get("BASE_URL", default and default.base_url),
        api_key=get("API_KEY", default and default.api_key),
        model=get("MODEL", default and default.model),
        extra_body=json.loads(extra) if extra else (default.extra_body if default else {}),
    )


LLM = _llm_config("LLM")
JUDGE = _llm_config("JUDGE", default=LLM)

# ── Retrieval ────────────────────────────────────────────────────────────────
TOP_K = 5  # results per Qdrant query
MAX_CONTEXT_TOKENS = 2000
