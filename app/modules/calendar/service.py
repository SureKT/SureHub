from datetime import datetime
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlmodel import Session, select

from app.config import settings
from app.modules.calendar.models import GoogleToken

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]

# Single-user: guardamos el flow entre /oauth/init y /oauth/callback
_pending_flow: Optional[Flow] = None


def _build_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    return flow


def get_auth_url() -> str:
    global _pending_flow
    _pending_flow = _build_flow()
    auth_url, _ = _pending_flow.authorization_url(prompt="consent", access_type="offline")
    return auth_url


def exchange_code(code: str, session: Session) -> GoogleToken:
    global _pending_flow
    if not _pending_flow:
        raise ValueError("No hay flow OAuth pendiente — visita /oauth/init primero")
    flow = _pending_flow
    _pending_flow = None
    flow.fetch_token(code=code)
    creds = flow.credentials

    token = session.exec(select(GoogleToken)).first()
    if not token:
        token = GoogleToken(
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            token_expiry=creds.expiry,
            token_uri=creds.token_uri,
            scopes=" ".join(creds.scopes or []),
        )
    else:
        token.access_token = creds.token
        if creds.refresh_token:
            token.refresh_token = creds.refresh_token
        token.token_expiry = creds.expiry
        token.scopes = " ".join(creds.scopes or [])
        token.updated_at = datetime.utcnow()

    session.add(token)
    session.commit()
    session.refresh(token)
    return token


def _get_credentials(session: Session) -> Optional[Credentials]:
    token = session.exec(select(GoogleToken)).first()
    if not token:
        return None

    creds = Credentials(
        token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri=token.token_uri,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=token.scopes.split(" ") if token.scopes else SCOPES,
    )
    creds.expiry = token.token_expiry

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token.access_token = creds.token
        token.token_expiry = creds.expiry
        token.updated_at = datetime.utcnow()
        session.add(token)
        session.commit()

    return creds


def is_connected(session: Session) -> bool:
    return session.exec(select(GoogleToken)).first() is not None


def create_event(
    session: Session,
    summary: str,
    start: str,
    end: str,
    description: str = "",
) -> dict:
    """
    start/end: ISO 8601 con timezone, e.g. "2026-06-25T10:00:00"
    """
    creds = _get_credentials(session)
    if not creds:
        raise ValueError("Google Calendar no conectado")

    service = build("calendar", "v3", credentials=creds)
    body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start, "timeZone": settings.TIMEZONE},
        "end": {"dateTime": end, "timeZone": settings.TIMEZONE},
    }
    return service.events().insert(calendarId="primary", body=body).execute()
