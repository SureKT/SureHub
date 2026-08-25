import time
from dataclasses import dataclass

import litellm

from app.config import settings

# Tier -> ordered model list (primary first, rest are fallbacks).
# "local_ok" prefers the local Ollama model when OLLAMA_BASE_URL is set and
# falls back to Haiku; without it the tier stays cloud-only.
def _local_ok_models() -> list[str]:
    cloud = f"anthropic/{settings.TAG_MODEL}"
    if settings.OLLAMA_BASE_URL:
        return [f"ollama_chat/{settings.OLLAMA_MODEL}", cloud]
    return [cloud]


TIERS: dict[str, list[str]] = {
    "cloud": [f"anthropic/{settings.LLM_MODEL}"],
    "local_ok": _local_ok_models(),
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


def _kwargs_for(model: str) -> dict:
    # Ollama needs its own base URL and a short timeout so a stalled local
    # model degrades to cloud instead of hanging the bot.
    if model.startswith("ollama"):
        return {
            "api_base": settings.OLLAMA_BASE_URL,
            "timeout": settings.LLM_LOCAL_TIMEOUT,
        }
    return {}


def complete(messages: list[dict], tier: str, max_tokens: int) -> RouterResult:
    models = TIERS[tier]
    primary = models[0]

    # Fallback done here, not with litellm's `fallbacks=`: that path reuses the
    # same kwargs for every candidate, so the local api_base would leak into the
    # Anthropic retry and break exactly when the fallback is needed.
    start = time.monotonic()
    resp = None
    last_error: Exception | None = None
    for model in models:
        try:
            resp = litellm.completion(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                **_kwargs_for(model),
            )
            break
        except Exception as e:
            last_error = e
    if resp is None:
        raise last_error
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
