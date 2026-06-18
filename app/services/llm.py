import anthropic
from app.config import settings

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

SYSTEM_BASE = (
    "Eres SureHub, asistente personal. "
    "Respuestas telegráficas: sin emojis, sin saludos, sin relleno, sin formalismos. "
    "Fragmentos si bastan. Directo al dato. "
    "Si usas formato, solo el de Telegram: *negrita*, _cursiva_, `código`. "
    "Nunca uses ## ni ** ni otros Markdown estándar."
)


def chat(mensaje: str, contexto_memoria: str = "", contexto_finanzas: str = "") -> str:
    system = SYSTEM_BASE
    if contexto_memoria:
        system += f"\n\n{contexto_memoria}"
    if contexto_finanzas:
        system += f"\n\n{contexto_finanzas}"

    response = client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": mensaje}],
    )
    return response.content[0].text


def complete_tags(prompt: str) -> str:
    """Lightweight LLM call for note tagging — no system prompt, Haiku, low max_tokens."""
    response = client.messages.create(
        model=settings.TAG_MODEL,
        max_tokens=128,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def complete_event(prompt: str) -> str:
    """Extracción de fecha/hora de eventos — Sonnet (mejor con fechas relativas)."""
    response = client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
