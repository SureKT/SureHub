from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Session, select

from app.config import settings
from app.modules.calendar.models import GoogleToken, OAuthPending

if TYPE_CHECKING:  # solo para type hints; no carga las libs Google en import
    from google.oauth2.credentials import Credentials

# OAuth scope alineado con app/services/calendar.py (solo escritura de eventos)
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _build_flow():
    # Import lazy: las libs Google solo se cargan en runtime, no al importar la app.
    from google_auth_oauthlib.flow import Flow

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


def get_auth_url(session: Session) -> str:
    flow = _build_flow()
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

    # Extraer code_verifier generado por la librería y persistirlo en DB
    code_verifier = getattr(flow, "code_verifier", None) or getattr(
        flow.oauth2session, "_code_verifier", None
    )
    if code_verifier:
        # Limpiar pendientes anteriores: solo puede haber un flow OAuth en curso
        for old in session.exec(select(OAuthPending)).all():
            session.delete(old)
        session.add(OAuthPending(code_verifier=code_verifier))
        session.commit()

    return auth_url


def exchange_code(code: str, session: Session) -> GoogleToken:
    pending = session.exec(select(OAuthPending)).first()
    code_verifier = pending.code_verifier if pending else None

    flow = _build_flow()
    flow.fetch_token(code=code, code_verifier=code_verifier)
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


def get_credentials(session: Session) -> Optional["Credentials"]:
    """Credenciales Google vivas (refresca si expiraron). Las usa
    app/services/calendar.py para hablar con la Calendar API."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

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
