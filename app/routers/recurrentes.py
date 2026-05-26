from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session
from app.database import get_session
from app.modules.finanzas.service import (
    list_recurring, create_recurring, generate_recurring
)

router = APIRouter(prefix="/api/finance/recurring", tags=["recurring"])


class RecurringCreate(BaseModel):
    name: str
    amount: float
    category_id: int | None = None
    day: int = 1


class RecurringUpdate(BaseModel):
    name: str | None = None
    amount: float | None = None
    category_id: int | None = None
    day: int | None = None
    active: bool | None = None


@router.get("")
def get_recurring(
    year: int | None = Query(None),
    month: int | None = Query(None),
    session: Session = Depends(get_session),
):
    return list_recurring(session, year, month)


@router.post("", status_code=201)
def post_recurring(body: RecurringCreate, session: Session = Depends(get_session)):
    if not 1 <= body.day <= 28:
        raise HTTPException(400, "day must be between 1 and 28")
    return create_recurring(session, body.name, body.amount, body.category_id, body.day)


@router.patch("/{id}")
def patch_recurring(id: int, body: RecurringUpdate, session: Session = Depends(get_session)):
    from app.modules.finanzas.models import RecurringExpense
    r = session.get(RecurringExpense, id)
    if not r:
        raise HTTPException(404)
    if body.name is not None:
        r.name = body.name
    if body.amount is not None:
        r.amount = body.amount
    if body.category_id is not None:
        r.category_id = body.category_id
    if body.day is not None:
        if not 1 <= body.day <= 28:
            raise HTTPException(400, "day must be between 1 and 28")
        r.day = body.day
    if body.active is not None:
        r.active = body.active
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


@router.delete("/{id}", status_code=204)
def delete_recurring(id: int, session: Session = Depends(get_session)):
    from app.modules.finanzas.models import RecurringExpense
    r = session.get(RecurringExpense, id)
    if not r:
        raise HTTPException(404)
    session.delete(r)
    session.commit()


@router.post("/generate", status_code=201)
def post_generate(
    year: int | None = Query(None),
    month: int | None = Query(None),
    session: Session = Depends(get_session),
):
    return generate_recurring(session, year, month)
