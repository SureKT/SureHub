from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session
from app.database import get_session
from app.modules.memoria.service import save_memory, list_memories, delete_memory, update_memory

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryCreate(BaseModel):
    fact: str


@router.get("")
def get_memories(session: Session = Depends(get_session)):
    return list_memories(session)


@router.post("", status_code=201)
def post_memory(body: MemoryCreate, session: Session = Depends(get_session)):
    return save_memory(session, body.fact)


@router.patch("/{id}")
def patch_memory(id: int, body: MemoryCreate, session: Session = Depends(get_session)):
    m = update_memory(session, id, body.fact)
    if not m:
        raise HTTPException(404)
    return m


@router.delete("/{id}", status_code=204)
def delete_memory_route(id: int, session: Session = Depends(get_session)):
    if not delete_memory(session, id):
        raise HTTPException(404)
