from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session
from app.database import get_session
from app.modules.memoria.service import guardar_memoria, listar_memorias, borrar_memoria

router = APIRouter(prefix="/api/memoria", tags=["memoria"])


class MemoriaCreate(BaseModel):
    hecho: str


@router.get("")
def get_memorias(session: Session = Depends(get_session)):
    return listar_memorias(session)


@router.post("", status_code=201)
def post_memoria(body: MemoriaCreate, session: Session = Depends(get_session)):
    return guardar_memoria(session, body.hecho)


@router.delete("/{id}", status_code=204)
def delete_memoria(id: int, session: Session = Depends(get_session)):
    if not borrar_memoria(session, id):
        raise HTTPException(404)
