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
