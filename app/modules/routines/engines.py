"""Execution engines for routines.

- litellm: single LLM call through llm_router (logged in llm_calls). Default.
- claude_code: headless `claude -p` agent with read-only tools. Needs the CLI and
  its credentials where it runs; not available in the prod containers yet.
"""
import json
import subprocess
from dataclasses import dataclass
from typing import Callable

from app.services import llm


class EngineError(RuntimeError):
    pass


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


def claude_code_command(prompt: str, *, allowed_tools: tuple[str, ...], model: str,
                        max_budget_usd: float, system: str = "") -> list[str]:
    cmd = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--model", model,
        "--allowedTools", ",".join(allowed_tools),
        "--max-budget-usd", str(max_budget_usd),
        "--no-session-persistence",
        # Without these the user's global hooks, plugins and MCP servers load into
        # every run: measured ~5x the cost of a trivial prompt and nondeterministic.
        "--setting-sources", "project",
        "--strict-mcp-config",
    ]
    if system:
        cmd += ["--append-system-prompt", system]
    return cmd


def run_claude_code(prompt: str, *, cwd: str, system: str = "",
                    allowed_tools: tuple[str, ...] = ("Read", "Glob", "Grep"),
                    model: str = "sonnet", timeout: int = 600, max_budget_usd: float = 1.0,
                    runner: Callable = subprocess.run) -> EngineResult:
    cmd = claude_code_command(prompt, allowed_tools=allowed_tools, model=model,
                              max_budget_usd=max_budget_usd, system=system)
    try:
        proc = runner(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as e:
        raise EngineError("claude CLI no disponible en este entorno") from e
    except subprocess.TimeoutExpired as e:
        raise EngineError(f"claude -p superó el timeout de {timeout}s") from e

    try:
        data = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError) as e:
        detail = (proc.stderr or proc.stdout or "").strip()[:500]
        raise EngineError(f"claude -p salida no JSON (rc={proc.returncode}): {detail}") from e

    if proc.returncode != 0 or data.get("is_error"):
        raise EngineError(f"claude -p falló: {str(data.get('result', ''))[:500]}")
    return EngineResult(text=data.get("result", ""), cost_usd=float(data.get("total_cost_usd") or 0.0),
                        model=model)


def run_engine(engine: str, prompt: str, *, system: str = "", cwd: str = ".",
               function: str = "routine") -> EngineResult:
    if engine == "litellm":
        return run_litellm(prompt, system=system, function=function)
    if engine == "claude_code":
        return run_claude_code(prompt, cwd=cwd, system=system)
    raise EngineError(f"Motor desconocido: {engine}")
