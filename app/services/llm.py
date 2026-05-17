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


def chat(mensaje: str, contexto_memoria: str = "") -> str:
    system = SYSTEM_BASE
    if contexto_memoria:
        system += f"\n\n{contexto_memoria}"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": mensaje}],
    )
    return response.content[0].text
