from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import settings

# Mapeo temática → colorId de Google Calendar (eventColors). Editable a mano.
CALENDAR_COLORS = {
    "coach":     "3",   # Grape    — coaching
    "formacion": "4",   # Flamingo — clase IA / proyectos de trabajo
    "social":    "5",   # Banana   — ocio con amigos
    "gimnasio":  "9",   # Blueberry — entreno rutinario
    "padel":     "10",  # Basil    — pádel / deporte de club
    "salud":     "11",  # Tomato   — médico, vacunas
    "default":   "8",   # Graphite — sin categorizar
}


def _event_body(summary: str, start: str, end: str, all_day: bool, theme: str,
                private: dict | None = None, description: str = "") -> dict:
    color = CALENDAR_COLORS.get(theme, CALENDAR_COLORS["default"])
    body = {"summary": summary, "colorId": color}
    if description:
        body["description"] = description
    if private:
        # extendedProperties.private: invisible en la UI, permite reconocer y
        # deshacer en lote los eventos que creó SureHub.
        body["extendedProperties"] = {"private": {k: str(v) for k, v in private.items()}}
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


def create_event(summary: str, start: str, end: str, all_day: bool, theme: str,
                 private: dict | None = None, description: str = "") -> tuple[str, str]:
    """Crea el evento en Google Calendar. Devuelve (event_id, html_link)."""
    body = _event_body(summary, start, end, all_day, theme, private, description)
    ev = _service().events().insert(
        calendarId=settings.GOOGLE_CALENDAR_ID, body=body
    ).execute()
    return ev["id"], ev.get("htmlLink", "")


def delete_event(event_id: str) -> None:
    from googleapiclient.errors import HttpError

    try:
        _service().events().delete(calendarId=settings.GOOGLE_CALENDAR_ID, eventId=event_id).execute()
    except HttpError as e:
        # 404/410: ya borrado a mano → el objetivo (que no exista) ya se cumple
        if e.resp.status not in (404, 410):
            raise


def _parse_event(raw: dict) -> dict:
    """Evento de la API → dict plano con horas locales naive ('YYYY-MM-DDTHH:MM:SS')."""
    start, end = raw.get("start", {}), raw.get("end", {})
    all_day = "date" in start
    if all_day:
        s, e = start["date"], end.get("date", start["date"])
    else:
        tz = ZoneInfo(settings.TIMEZONE)
        s = datetime.fromisoformat(start["dateTime"]).astimezone(tz).replace(tzinfo=None).isoformat()
        e = datetime.fromisoformat(end["dateTime"]).astimezone(tz).replace(tzinfo=None).isoformat()
    private = raw.get("extendedProperties", {}).get("private", {})
    return {
        "id": raw.get("id", ""),
        "summary": raw.get("summary", "(sin título)"),
        "start": s,
        "end": e,
        "all_day": all_day,
        "color_id": raw.get("colorId"),
        "description": raw.get("description", ""),
        "recurring": bool(raw.get("recurringEventId")),
        "surehub_run": private.get("surehub_run"),
    }


def list_events(start: date, end: date) -> list[dict]:
    """Eventos (recurrentes expandidos) entre start y end, ambos días incluidos."""
    tz = ZoneInfo(settings.TIMEZONE)
    time_min = datetime.combine(start, datetime.min.time(), tz).isoformat()
    time_max = datetime.combine(end + timedelta(days=1), datetime.min.time(), tz).isoformat()
    resp = _service().events().list(
        calendarId=settings.GOOGLE_CALENDAR_ID, timeMin=time_min, timeMax=time_max,
        singleEvents=True, orderBy="startTime", maxResults=250,
    ).execute()
    return [_parse_event(ev) for ev in resp.get("items", [])]
