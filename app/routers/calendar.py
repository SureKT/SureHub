from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
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


class EventIn(BaseModel):
    summary: str
    start: str  # ISO 8601, e.g. "2026-06-25T10:00:00"
    end: str
    description: str = ""


@router.post("/events")
def create_event(body: EventIn, session: Session = Depends(get_session)):
    try:
        event = cal.create_event(session, body.summary, body.start, body.end, body.description)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"id": event["id"], "link": event.get("htmlLink")}
