from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session
from app.database import get_session
from app.modules.finanzas.service import (
    listar_recurrentes, crear_recurrente, generar_recurrentes
)

router = APIRouter(prefix="/api/finanzas/recurrentes", tags=["recurrentes"])


class RecurrenteCreate(BaseModel):
    nombre: str
    cantidad: float
    categoria_id: int | None = None
    dia: int = 1


class RecurrenteUpdate(BaseModel):
    nombre: str | None = None
    cantidad: float | None = None
    categoria_id: int | None = None
    dia: int | None = None
    activo: bool | None = None


@router.get("")
def get_recurrentes(
    anio: int | None = Query(None),
    mes: int | None = Query(None),
    session: Session = Depends(get_session),
):
    return listar_recurrentes(session, anio, mes)


@router.post("", status_code=201)
def post_recurrente(body: RecurrenteCreate, session: Session = Depends(get_session)):
    if not 1 <= body.dia <= 28:
        raise HTTPException(400, "dia debe estar entre 1 y 28")
    return crear_recurrente(session, body.nombre, body.cantidad, body.categoria_id, body.dia)


@router.patch("/{id}")
def patch_recurrente(id: int, body: RecurrenteUpdate, session: Session = Depends(get_session)):
    from app.modules.finanzas.models import GastoRecurrente
    r = session.get(GastoRecurrente, id)
    if not r:
        raise HTTPException(404)
    if body.nombre is not None:
        r.nombre = body.nombre
    if body.cantidad is not None:
        r.cantidad = body.cantidad
    if body.categoria_id is not None:
        r.categoria_id = body.categoria_id
    if body.dia is not None:
        if not 1 <= body.dia <= 28:
            raise HTTPException(400, "dia debe estar entre 1 y 28")
        r.dia = body.dia
    if body.activo is not None:
        r.activo = body.activo
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


@router.delete("/{id}", status_code=204)
def delete_recurrente(id: int, session: Session = Depends(get_session)):
    from app.modules.finanzas.models import GastoRecurrente
    r = session.get(GastoRecurrente, id)
    if not r:
        raise HTTPException(404)
    session.delete(r)
    session.commit()


@router.post("/generar", status_code=201)
def post_generar(
    anio: int | None = Query(None),
    mes: int | None = Query(None),
    session: Session = Depends(get_session),
):
    return generar_recurrentes(session, anio, mes)
