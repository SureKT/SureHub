"""LLM call for routines, through llm_router (cost logged in llm_calls)."""
from dataclasses import dataclass

from app.services import llm


@dataclass
class EngineResult:
    text: str
    cost_usd: float = 0.0
    model: str = ""


def run_litellm(prompt: str, *, system: str = "", tier: str = "cloud",
                max_tokens: int = 4000, function: str = "routine") -> EngineResult:
    result = llm.complete_routine(prompt, system=system, tier=tier,
                                  max_tokens=max_tokens, function=function)
    return EngineResult(text=result.text, cost_usd=result.cost_usd, model=result.model_served)
