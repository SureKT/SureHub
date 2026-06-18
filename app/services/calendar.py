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

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


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
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(settings.GOOGLE_CALENDAR_TOKEN, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def create_event(summary: str, start: str, end: str, all_day: bool, theme: str) -> tuple[str, str]:
    """Crea el evento en Google Calendar. Devuelve (event_id, html_link)."""
    body = _event_body(summary, start, end, all_day, theme)
    ev = _service().events().insert(
        calendarId=settings.GOOGLE_CALENDAR_ID, body=body
    ).execute()
    return ev["id"], ev.get("htmlLink", "")
