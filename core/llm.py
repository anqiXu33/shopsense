"""core/llm.py

The one place that talks to a language model. Every caller goes through
complete(), which sends an OpenAI-compatible /chat/completions request built
from the LLM_* (or JUDGE_*) settings in .env, so swapping OpenAI for DeepSeek
or a local Ollama model is a configuration change only.

Only parameters every provider understands are sent (model, messages,
response_format, tools); anything model-specific (reasoning effort,
temperature …) comes from LLM_EXTRA_BODY. Errors propagate: a failed call
raises.

Token usage is tallied per model in USAGE so scripts can report cost.
"""

import json
from collections import Counter, defaultdict

import requests

from config.settings import LLM, LLMConfig

USAGE: dict = defaultdict(Counter)


def complete(body: dict, config: LLMConfig = LLM, timeout: int = 300) -> dict:
    """Send one chat request; return the assistant message."""
    resp = requests.post(
        f"{config.base_url}/chat/completions",
        headers={"Authorization": f"Bearer {config.api_key}"},
        json={"model": config.model, **body, **config.extra_body},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    _tally(config.model, data["usage"])
    return data["choices"][0]["message"]


def _tally(model: str, usage: dict) -> None:
    # Providers differ in how much detail they report; the two totals are
    # always there, the breakdowns only on some (OpenAI, DeepSeek).
    u = USAGE[model]
    u["requests"] += 1
    u["prompt_tokens"] += usage["prompt_tokens"]
    u["completion_tokens"] += usage["completion_tokens"]
    u["cached_tokens"] += (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
    u["reasoning_tokens"] += (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0


def chat(messages: list, *, schema: dict | None = None, config: LLMConfig = LLM) -> str:
    """
    One completion. With `schema`, decoding is constrained to that JSON
    schema (strict structured output), so the model cannot invent keys or
    tag names.
    """
    body = {"messages": messages}
    if schema is not None:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "reply", "schema": schema, "strict": True},
        }
    return complete(body, config)["content"].strip()


def chat_json(messages: list, schema: dict, *, config: LLMConfig = LLM) -> dict:
    return json.loads(chat(messages, schema=schema, config=config))


def object_schema(properties: dict) -> dict:
    """A closed JSON object schema in which every property is required."""
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def usage_summary() -> dict:
    return {model: dict(c) for model, c in USAGE.items()}
