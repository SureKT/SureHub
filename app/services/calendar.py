from datetime import date, timedelta

from app.config import settings

# Mapeo temática → colorId de Google Calendar (eventColors). Editable a mano.
CALENDAR_COLORS = {
    "coach":     "3",   # Grape    — Diana/coach
    "formacion": "4",   # Flamingo — clase IA / proyectos de trabajo
    "social":    "5",   # Banana   — ocio con amigos
    "gimnasio":  "9",   # Blueberry — entreno rutinario
    "padel":     "10",  # Basil    — pádel / deporte de club
    "default":   "8",   # Graphite — sin categorizar
}


def _event_body(summary: str, start: str, end: str, all_day: bool, theme: str) -> dict:
    color = CALENDAR_COLORS.get(theme, CALENDAR_COLORS["default"])
    body = {"summary": summary, "colorId": color}
    if all_day:
        end_excl = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
        body["start"] = {"date": start}
        body["end"] = {"date": end_excl}
    else:
        body["start"] = {"dateTime": start, "timeZone": settings.TIMEZONE}
        body["end"] = {"dateTime": end, "timeZone": settings.TIMEZONE}
    return body


def _service():
    # Imports lazy: las libs Google solo se cargan en runtime, no en tests del body.
    from googleapiclient.discovery import build

    from app.database import get_session
    from app.modules.calendar.service import get_credentials

    creds = get_credentials(next(get_session()))
    if not creds:
        raise ValueError("Google Calendar no conectado (visita /api/calendar/oauth/init)")
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def create_event(summary: str, start: str, end: str, all_day: bool, theme: str) -> tuple[str, str]:
    """Crea el evento en Google Calendar. Devuelve (event_id, html_link)."""
    body = _event_body(summary, start, end, all_day, theme)
    ev = _service().events().insert(
        calendarId=settings.GOOGLE_CALENDAR_ID, body=body
    ).execute()
    return ev["id"], ev.get("htmlLink", "")
