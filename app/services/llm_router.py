import time
from dataclasses import dataclass

import litellm

from app.config import settings

# Tier -> ordered model list (primary first, rest are fallbacks).
# Phase 1: every tier is cloud-only and matches today's models exactly.
# Phase 2 will prepend the Ollama model to "local_ok".
TIERS: dict[str, list[str]] = {
    "cloud": [f"anthropic/{settings.LLM_MODEL}"],
    "local_ok": [f"anthropic/{settings.TAG_MODEL}"],
}


@dataclass
class RouterResult:
    text: str
    model_requested: str
    model_served: str
    fell_back: bool
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int


def _base(model: str) -> str:
    return model.split("/")[-1]


def complete(messages: list[dict], tier: str, max_tokens: int) -> RouterResult:
    models = TIERS[tier]
    primary, fallbacks = models[0], models[1:]

    start = time.monotonic()
    resp = litellm.completion(
        model=primary,
        messages=messages,
        max_tokens=max_tokens,
        fallbacks=fallbacks or None,
    )
    latency_ms = int((time.monotonic() - start) * 1000)

    served = resp.model
    # Anthropic resolves an alias (claude-haiku-4-5) to a dated snapshot
    # (claude-haiku-4-5-20251001), so match by prefix, not equality, or every
    # Haiku call would look like a fallback.
    fell_back = not _base(served).startswith(_base(primary))
    try:
        cost = float(litellm.completion_cost(completion_response=resp))
    except Exception:
        cost = 0.0

    return RouterResult(
        text=resp.choices[0].message.content,
        model_requested=primary,
        model_served=served,
        fell_back=fell_back,
        input_tokens=resp.usage.prompt_tokens,
        output_tokens=resp.usage.completion_tokens,
        cost_usd=cost,
        latency_ms=latency_ms,
    )
