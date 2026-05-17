import anthropic
from app.config import settings

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def chat(mensaje: str, system: str = "Eres SureHub, asistente personal. Respuestas concisas.") -> str:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": mensaje}],
    )
    return response.content[0].text
