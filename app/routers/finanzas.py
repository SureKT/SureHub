from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session
from app.database import get_session
from app.modules.finanzas.service import (
    crear_categoria, listar_categorias, buscar_categoria,
    registrar_gasto, ultimos_gastos, resumen_mes, total_mes_global
)

router = APIRouter(prefix="/api/finanzas", tags=["finanzas"])


class CategoriaCreate(BaseModel):
    nombre: str
    tipo: str
    estimacion_mensual: float = 0.0


class CategoriaUpdate(BaseModel):
    estimacion_mensual: float | None = None
    activa: bool | None = None


class GastoCreate(BaseModel):
    categoria_id: int | None = None
    cantidad: float
    descripcion: str | None = None


@router.get("/categorias")
def get_categorias(session: Session = Depends(get_session)):
    return listar_categorias(session)


@router.post("/categorias", status_code=201)
def post_categoria(body: CategoriaCreate, session: Session = Depends(get_session)):
    if buscar_categoria(session, body.nombre):
        raise HTTPException(400, "Categoría ya existe")
    return crear_categoria(session, body.nombre, body.tipo, body.estimacion_mensual)


@router.patch("/categorias/{id}")
def patch_categoria(id: int, body: CategoriaUpdate, session: Session = Depends(get_session)):
    from app.modules.finanzas.models import Categoria
    cat = session.get(Categoria, id)
    if not cat:
        raise HTTPException(404)
    if body.estimacion_mensual is not None:
        cat.estimacion_mensual = body.estimacion_mensual
    if body.activa is not None:
        cat.activa = body.activa
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


@router.delete("/categorias/{id}", status_code=204)
def delete_categoria(id: int, session: Session = Depends(get_session)):
    from app.modules.finanzas.models import Categoria
    cat = session.get(Categoria, id)
    if not cat:
        raise HTTPException(404)
    session.delete(cat)
    session.commit()


@router.get("/gastos")
def get_gastos(n: int = 50, session: Session = Depends(get_session)):
    gastos = ultimos_gastos(session, n)
    return [
        {
            "id": g.id,
            "cantidad": g.cantidad,
            "descripcion": g.descripcion,
            "fecha": g.fecha,
            "fuente": g.fuente,
            "categoria": {"id": cat.id, "nombre": cat.nombre} if cat else None,
        }
        for g, cat in gastos
    ]


@router.post("/gastos", status_code=201)
def post_gasto(body: GastoCreate, session: Session = Depends(get_session)):
    return registrar_gasto(session, body.cantidad, body.categoria_id, body.descripcion, "manual")


@router.get("/resumen")
def get_resumen(session: Session = Depends(get_session)):
    return {
        "categorias": resumen_mes(session),
        "total": total_mes_global(session),
    }
