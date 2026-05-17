from sqlmodel import Session, select
from app.modules.memoria.models import Memoria


def guardar_memoria(session: Session, hecho: str) -> Memoria:
    memoria = Memoria(hecho=hecho)
    session.add(memoria)
    session.commit()
    session.refresh(memoria)
    return memoria


def listar_memorias(session: Session) -> list[Memoria]:
    return list(session.exec(select(Memoria).order_by(Memoria.fecha)).all())


def borrar_memoria(session: Session, id: int) -> bool:
    memoria = session.get(Memoria, id)
    if not memoria:
        return False
    session.delete(memoria)
    session.commit()
    return True


def construir_contexto(session: Session) -> str:
    memorias = listar_memorias(session)
    if not memorias:
        return ""
    hechos = "\n".join(f"- {m.hecho}" for m in memorias)
    return f"Lo que sabes del usuario:\n{hechos}"
