from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from app.database import get_session
from app.modules.calendar import service as cal

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/oauth/init")
def oauth_init(session: Session = Depends(get_session)):
    return RedirectResponse(cal.get_auth_url(session))


@router.get("/oauth/callback")
def oauth_callback(code: str, session: Session = Depends(get_session)):
    cal.exchange_code(code, session)
    return HTMLResponse(
        "<h2>Google Calendar conectado ✅</h2><p>Puedes cerrar esta pestaña.</p>"
    )


@router.get("/status")
def status(session: Session = Depends(get_session)):
    return {"connected": cal.is_connected(session)}
