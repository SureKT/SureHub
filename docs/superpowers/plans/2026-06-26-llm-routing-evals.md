# LLM Routing + Evals — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route SureHub's LLM calls through LiteLLM with per-tier model selection and fallback, logging every call to SQLite — without changing the public interface of `llm.py` or its callers.

**Architecture:** `llm.py` keeps its 3 public functions (`chat`, `complete_tags`, `complete_event`); each declares a *tier*. A new `llm_router.complete()` resolves the tier to a LiteLLM model list and calls it. A `_log` wrapper persists call metadata to a new `llm_calls` table. Phase 1 sends everything to the same Anthropic models as today (no behavior change) — it only adds the abstraction + observability. Local routing (Ollama) and evals (promptfoo) are Phases 2 & 3, planned separately.

**Tech Stack:** Python, LiteLLM, SQLModel, SQLite, pytest.

**Scope of THIS plan:** Phase 1 only (LiteLLM abstraction + SQLite logging). See spec `docs/superpowers/specs/2026-06-26-llm-routing-evals-design.md`.

---

## File Structure

- Create: `app/services/llm_router.py` — tier→model config + `complete()` over LiteLLM. One job: turn (messages, tier) into a `RouterResult`.
- Create: `app/modules/llm_log/__init__.py` — empty package marker.
- Create: `app/modules/llm_log/models.py` — `LLMCall` SQLModel table.
- Create: `app/modules/llm_log/service.py` — `log_call(session, **fields)`.
- Modify: `app/models.py` — import `LLMCall` so `create_db()` creates the table.
- Modify: `app/services/llm.py` — route the 3 functions through `llm_router` + `_log`.
- Modify: `.env.example` — document new vars.
- Modify: `CLAUDE.md` — note the LLM layer now goes through LiteLLM.
- Test: `tests/test_llm_router.py`, `tests/test_llm_log.py`, `tests/test_llm_wiring.py`.

---

## Task 1: Add LiteLLM + validate it reaches Anthropic

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the dependency**

Append to `requirements.txt`:

```
litellm>=1.40.0
```

- [ ] **Step 2: Install**

Run: `.venv/bin/python -m pip install -r requirements.txt`
(If pip missing in venv, run `python3 -m pip install --target .venv/lib/python3.12/site-packages litellm` or install via the project's normal tooling.)
Expected: litellm installs without error.

- [ ] **Step 3: Validation spike — confirm the Anthropic model string**

This locks the exact LiteLLM model string used everywhere below. Run from repo root with venv active and a real `ANTHROPIC_API_KEY` in `.env`:

```bash
.venv/bin/python -c "
import litellm, os
from app.config import settings
m = f'anthropic/{settings.LLM_MODEL}'
r = litellm.completion(model=m, messages=[{'role':'user','content':'say ok'}], max_tokens=5)
print('MODEL_REQUESTED:', m)
print('MODEL_SERVED:', r.model)
print('TEXT:', r.choices[0].message.content)
print('COST:', litellm.completion_cost(completion_response=r))
"
```

Expected: prints a short reply, a non-empty `MODEL_SERVED`, and a small float cost. If LiteLLM rejects `anthropic/<id>`, try the bare `settings.LLM_MODEL` and record which form works — that form is what Task 4's `TIERS` must use.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add litellm dependency"
```

---

## Task 2: `LLMCall` model + `log_call` service

**Files:**
- Create: `app/modules/llm_log/__init__.py`
- Create: `app/modules/llm_log/models.py`
- Create: `app/modules/llm_log/service.py`
- Test: `tests/test_llm_log.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_llm_log.py`:

```python
from sqlmodel import select

from app.modules.llm_log.models import LLMCall
from app.modules.llm_log.service import log_call


def test_log_call_persists_row(session):
    call = log_call(
        session,
        function="complete_tags",
        tier="local_ok",
        model_requested="anthropic/haiku",
        model_served="anthropic/haiku",
        fell_back=False,
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.0001,
        latency_ms=120,
        prompt="some prompt",
        output="some output",
        success=True,
        error=None,
    )
    assert call.id is not None
    rows = session.exec(select(LLMCall)).all()
    assert len(rows) == 1
    assert rows[0].function == "complete_tags"
    assert rows[0].fell_back is False
    assert rows[0].cost_usd == 0.0001
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_llm_log.py -q`
Expected: FAIL — `ModuleNotFoundError: app.modules.llm_log`.

- [ ] **Step 3: Create the package marker**

Create `app/modules/llm_log/__init__.py` (empty file).

- [ ] **Step 4: Create the model**

Create `app/modules/llm_log/models.py`:

```python
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class LLMCall(SQLModel, table=True):
    __tablename__ = "llm_calls"

    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    function: str
    tier: str
    model_requested: str
    model_served: str = ""
    fell_back: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    prompt: str = ""
    output: str = ""
    success: bool = True
    error: str | None = None
```

- [ ] **Step 5: Create the service**

Create `app/modules/llm_log/service.py`:

```python
from sqlmodel import Session

from app.modules.llm_log.models import LLMCall


def log_call(session: Session, **fields) -> LLMCall:
    call = LLMCall(**fields)
    session.add(call)
    session.commit()
    session.refresh(call)
    return call
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_llm_log.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/modules/llm_log tests/test_llm_log.py
git commit -m "feat(llm-log): LLMCall model + log_call service"
```

---

## Task 3: Register `LLMCall` so `create_db()` creates the table

**Files:**
- Modify: `app/models.py`
- Test: `tests/test_llm_log.py` (add a table-creation assertion)

Note: `llm_calls` is a brand-new table. SQLModel `create_all` creates missing tables on next boot — no ALTER/migration needed for the existing prod DB.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_llm_log.py`:

```python
def test_llmcall_registered_in_metadata():
    import app.models  # noqa: F401
    from sqlmodel import SQLModel

    assert "llm_calls" in SQLModel.metadata.tables
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_llm_log.py::test_llmcall_registered_in_metadata -q`
Expected: FAIL — `llm_calls` not in metadata (not imported by `app.models` yet).

(It may already pass if Task 2's test imported the model first; if so, still add the import below to guarantee `create_db()` sees it independently of test import order.)

- [ ] **Step 3: Add the import**

In `app/models.py`, add alongside the other model imports:

```python
from app.modules.llm_log.models import LLMCall  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_llm_log.py -q`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_llm_log.py
git commit -m "feat(llm-log): register LLMCall for create_db"
```

---

## Task 4: `llm_router.complete()`

**Files:**
- Create: `app/services/llm_router.py`
- Test: `tests/test_llm_router.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_llm_router.py`:

```python
from app.services import llm_router


class _FakeMsg:
    content = "hi there"


class _FakeChoice:
    message = _FakeMsg()


class _FakeUsage:
    prompt_tokens = 10
    completion_tokens = 3


class _FakeResp:
    model = "claude-haiku-4-5"
    choices = [_FakeChoice()]
    usage = _FakeUsage()


def test_complete_happy_path(monkeypatch):
    monkeypatch.setattr(llm_router.litellm, "completion", lambda **k: _FakeResp())
    monkeypatch.setattr(llm_router.litellm, "completion_cost", lambda **k: 0.0001)

    r = llm_router.complete(
        messages=[{"role": "user", "content": "x"}],
        tier="local_ok",
        max_tokens=128,
    )

    assert r.text == "hi there"
    assert r.input_tokens == 10
    assert r.output_tokens == 3
    assert r.cost_usd == 0.0001
    assert r.fell_back is False
    assert r.model_served == "claude-haiku-4-5"


def test_complete_cost_failure_defaults_to_zero(monkeypatch):
    def _boom(**k):
        raise RuntimeError("no pricing")

    monkeypatch.setattr(llm_router.litellm, "completion", lambda **k: _FakeResp())
    monkeypatch.setattr(llm_router.litellm, "completion_cost", _boom)

    r = llm_router.complete(
        messages=[{"role": "user", "content": "x"}],
        tier="local_ok",
        max_tokens=128,
    )
    assert r.cost_usd == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_llm_router.py -q`
Expected: FAIL — `app.services.llm_router` does not exist.

- [ ] **Step 3: Implement the router**

Create `app/services/llm_router.py`:

```python
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
    try:
        cost = float(litellm.completion_cost(completion_response=resp))
    except Exception:
        cost = 0.0

    return RouterResult(
        text=resp.choices[0].message.content,
        model_requested=primary,
        model_served=served,
        fell_back=_base(served) != _base(primary),
        input_tokens=resp.usage.prompt_tokens,
        output_tokens=resp.usage.completion_tokens,
        cost_usd=cost,
        latency_ms=latency_ms,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_llm_router.py -q`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/llm_router.py tests/test_llm_router.py
git commit -m "feat(llm-router): tier-based complete() over LiteLLM"
```

---

## Task 5: Wire `llm.py` through the router + logging

**Files:**
- Modify: `app/services/llm.py`
- Test: `tests/test_llm_wiring.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_llm_wiring.py`:

```python
from app.services import llm, llm_router


def _fake_result(text):
    return llm_router.RouterResult(
        text=text,
        model_requested="anthropic/x",
        model_served="anthropic/x",
        fell_back=False,
        input_tokens=1,
        output_tokens=1,
        cost_usd=0.0,
        latency_ms=5,
    )


def test_complete_tags_returns_router_text(monkeypatch):
    captured = {}

    def fake_complete(messages, tier, max_tokens):
        captured["tier"] = tier
        return _fake_result("tag1, tag2")

    monkeypatch.setattr(llm_router, "complete", fake_complete)
    monkeypatch.setattr(llm, "_log", lambda *a, **k: None)

    assert llm.complete_tags("hello note") == "tag1, tag2"
    assert captured["tier"] == "local_ok"


def test_chat_uses_cloud_tier(monkeypatch):
    captured = {}

    def fake_complete(messages, tier, max_tokens):
        captured["tier"] = tier
        captured["messages"] = messages
        return _fake_result("respuesta")

    monkeypatch.setattr(llm_router, "complete", fake_complete)
    monkeypatch.setattr(llm, "_log", lambda *a, **k: None)

    out = llm.chat("hola", contexto_memoria="memo")
    assert out == "respuesta"
    assert captured["tier"] == "cloud"
    # system message carries SYSTEM_BASE + injected context
    assert captured["messages"][0]["role"] == "system"
    assert "memo" in captured["messages"][0]["content"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_llm_wiring.py -q`
Expected: FAIL — `llm` has no `_log`, and functions still call the Anthropic client directly.

- [ ] **Step 3: Rewrite `llm.py`**

Replace the body of `app/services/llm.py` with:

```python
from app.database import get_session
from app.modules.llm_log.service import log_call
from app.services import llm_router

SYSTEM_BASE = (
    "Eres SureHub, asistente personal. "
    "Respuestas telegráficas: sin emojis, sin saludos, sin relleno, sin formalismos. "
    "Fragmentos si bastan. Directo al dato. "
    "Si usas formato, solo el de Telegram: *negrita*, _cursiva_, `código`. "
    "Nunca uses ## ni ** ni otros Markdown estándar."
)


def _log(function, tier, messages, result, error):
    """Persist call metadata. Must never raise into the caller."""
    try:
        session = next(get_session())
        prompt_txt = messages[-1]["content"][:4000]
        if result is not None:
            log_call(
                session,
                function=function,
                tier=tier,
                model_requested=result.model_requested,
                model_served=result.model_served,
                fell_back=result.fell_back,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_usd=result.cost_usd,
                latency_ms=result.latency_ms,
                prompt=prompt_txt,
                output=result.text[:4000],
                success=True,
                error=None,
            )
        else:
            log_call(
                session,
                function=function,
                tier=tier,
                model_requested=tier,
                model_served="",
                fell_back=False,
                prompt=prompt_txt,
                output="",
                success=False,
                error=error,
            )
    except Exception:
        pass


def _run(function, tier, messages, max_tokens):
    result = None
    error = None
    try:
        result = llm_router.complete(messages, tier, max_tokens)
        return result.text
    except Exception as e:
        error = str(e)
        raise
    finally:
        _log(function, tier, messages, result, error)


def chat(mensaje: str, contexto_memoria: str = "", contexto_finanzas: str = "") -> str:
    system = SYSTEM_BASE
    if contexto_memoria:
        system += f"\n\n{contexto_memoria}"
    if contexto_finanzas:
        system += f"\n\n{contexto_finanzas}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": mensaje},
    ]
    return _run("chat", "cloud", messages, max_tokens=1024)


def complete_tags(prompt: str) -> str:
    """Lightweight LLM call for note tagging. Tier local_ok (cloud in Phase 1)."""
    messages = [{"role": "user", "content": prompt}]
    return _run("complete_tags", "local_ok", messages, max_tokens=128)


def complete_event(prompt: str) -> str:
    """Date/time extraction for events. Tier cloud (needs the smart model)."""
    messages = [{"role": "user", "content": prompt}]
    return _run("complete_event", "cloud", messages, max_tokens=300)
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `.venv/bin/pytest tests/test_llm_wiring.py -q`
Expected: PASS (both tests).

- [ ] **Step 5: Run the modules that consume `llm.py` to confirm no regression**

Existing callers are `bot/handlers.py` and `bot/inbox_handlers.py`. Run their tests:

Run: `.venv/bin/pytest tests/test_bot_handlers.py tests/test_inbox_handlers.py tests/test_inbox_service.py tests/test_notes.py -q`
Expected: PASS. If any test patched `app.services.llm.client` (the removed Anthropic client), update it to patch `app.services.llm_router.complete` instead — same return contract (a string). Search first:

```bash
grep -rn "llm.client\|messages.create\|services.llm" tests/
```

- [ ] **Step 6: Full suite**

Run: `.venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/services/llm.py tests/test_llm_wiring.py
git commit -m "feat(llm): route chat/tags/event through LiteLLM router + log calls"
```

---

## Task 6: Config + `.env.example`

**Files:**
- Modify: `.env.example`

Phase 1 introduces no new *required* env vars (tiers reuse `LLM_MODEL`/`TAG_MODEL`). Document the vars Phase 2 will add so the surface is known.

- [ ] **Step 1: Document upcoming vars**

Append to `.env.example`:

```
# LLM routing (Phase 2 — Ollama local backend; unused in Phase 1)
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=qwen2.5:3b
# LLM_LOCAL_TIMEOUT=20
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: document Phase 2 Ollama env vars"
```

---

## Task 7: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Note the LLM layer change**

In `CLAUDE.md`, under "Decisiones de arquitectura", add:

```
- **Capa LLM vía LiteLLM** — `app/services/llm.py` no llama a la SDK de Anthropic directo; pasa por `app/services/llm_router.py` (tier→modelo + fallback) y cada llamada se loguea en `llm_calls` (SQLite). Tiers: `cloud` (sonnet) y `local_ok` (haiku; Ollama local en Fase 2). Spec: `docs/superpowers/specs/2026-06-26-llm-routing-evals-design.md`
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: note LiteLLM LLM layer in CLAUDE.md"
```

---

## Phase 2 & 3 — separate plans (do NOT start here)

These get their own plans **after Phase 1 ships**, because they depend on runtime facts that Phase 1 establishes:

- **Phase 2 (local routing):** install Ollama on `surehub-home` (CPU), pull `qwen2.5:3b`, validate LiteLLM's `ollama_chat/<model>` string + `OLLAMA_BASE_URL` reach it, then prepend the local model to `TIERS["local_ok"]` with a timeout and verify fallback (kill Ollama → call still succeeds via Haiku, logged `fell_back=true`). Infra doc lands in `SureKT/homelab`.
- **Phase 3 (evals + decision):** build `evals/` (real tagging dataset + `promptfooconfig.yaml`), run local vs Haiku vs Sonnet, write the results report, and apply the decision rule (local accuracy ≥ Haiku − 5pp → keep local routing; else revert tier to cloud and keep the report).

Re-invoke `writing-plans` for each once Phase 1 is merged.

---

## Self-Review

- **Spec coverage (Phase 1 scope):** LiteLLM abstraction (Tasks 4-5) ✓; SQLite logging (Tasks 2-3, 5) ✓; interface unchanged / callers intact (Task 5 steps 5-6) ✓; config surface (Task 6) ✓; docs (Task 7) ✓; tests with LiteLLM mocked, CI green without Ollama/API key (Tasks 2,4,5) ✓. Phases 2-3 explicitly deferred with rationale ✓.
- **Placeholders:** none — every code/test step shows full content; model-string ambiguity is resolved by Task 1's spike, not left open.
- **Type consistency:** `RouterResult` fields are identical across Task 4 (definition), Task 5 (`_fake_result`, `_log`), checked. `log_call(session, **fields)` signature consistent across Tasks 2 and 5. `complete(messages, tier, max_tokens)` signature consistent across Tasks 4 and 5.
