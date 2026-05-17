from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlmodel import Session
from app.database import get_session
from app.modules.finanzas.service import (
    crear_categoria, listar_categorias, buscar_categoria,
    registrar_gasto, get_gastos_filtrados, resumen_mes, total_mes_global,
    evolucion_mensual, meses_disponibles
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
    fecha: str | None = None  # ISO date string opcional


class GastoUpdate(BaseModel):
    categoria_id: int | None = None
    cantidad: float | None = None
    descripcion: str | None = None
    fecha: str | None = None


@router.get("/categorias")
def get_categorias(solo_activas: bool = Query(True), session: Session = Depends(get_session)):
    return listar_categorias(session, solo_activas=solo_activas)


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
def get_gastos(
    anio: int | None = Query(None),
    mes: int | None = Query(None),
    categoria_id: int | None = Query(None),
    busqueda: str | None = Query(None),
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=5000),
    orden: str = Query("fecha"),
    asc: bool = Query(False),
    session: Session = Depends(get_session),
):
    gastos, total = get_gastos_filtrados(session, anio, mes, categoria_id,
                                          busqueda, desde, hasta, page, per_page, orden, asc)
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
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
    }


@router.post("/gastos", status_code=201)
def post_gasto(body: GastoCreate, session: Session = Depends(get_session)):
    from datetime import datetime, timezone
    fecha = None
    if body.fecha:
        try:
            fecha = datetime.fromisoformat(body.fecha).replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(400, "Formato de fecha inválido")
    from app.modules.finanzas.models import Gasto
    gasto = Gasto(
        cantidad=body.cantidad,
        categoria_id=body.categoria_id,
        descripcion=body.descripcion,
        fuente="manual",
        **({"fecha": fecha} if fecha else {})
    )
    session.add(gasto)
    session.commit()
    session.refresh(gasto)
    return gasto


@router.patch("/gastos/{id}")
def patch_gasto(id: int, body: GastoUpdate, session: Session = Depends(get_session)):
    from app.modules.finanzas.models import Gasto
    from datetime import datetime, timezone
    gasto = session.get(Gasto, id)
    if not gasto:
        raise HTTPException(404)
    if body.cantidad is not None:
        gasto.cantidad = body.cantidad
    if body.descripcion is not None:
        gasto.descripcion = body.descripcion
    if body.categoria_id is not None:
        gasto.categoria_id = body.categoria_id
    if body.fecha is not None:
        try:
            gasto.fecha = datetime.fromisoformat(body.fecha).replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(400, "Formato de fecha inválido")
    session.add(gasto)
    session.commit()
    session.refresh(gasto)
    return gasto


@router.delete("/gastos/{id}", status_code=204)
def delete_gasto(id: int, session: Session = Depends(get_session)):
    from app.modules.finanzas.models import Gasto
    gasto = session.get(Gasto, id)
    if not gasto:
        raise HTTPException(404)
    session.delete(gasto)
    session.commit()


@router.get("/resumen")
def get_resumen(
    anio: int | None = Query(None),
    mes: int | None = Query(None),
    session: Session = Depends(get_session)
):
    return {
        "categorias": resumen_mes(session, anio, mes),
        "total": total_mes_global(session, anio, mes),
    }


@router.get("/evolucion")
def get_evolucion(meses: int = Query(12, ge=2, le=24), session: Session = Depends(get_session)):
    return evolucion_mensual(session, meses)


@router.get("/meses")
def get_meses(session: Session = Depends(get_session)):
    return meses_disponibles(session)


class ImportarRow(BaseModel):
    fecha: str | None = None
    descripcion: str | None = None
    cantidad: float
    categoria_id: int | None = None


@router.post("/importar/preview")
async def importar_preview(file: UploadFile = File(...), session: Session = Depends(get_session)):
    from app.modules.finanzas.importer import parse_ing_xls
    content = await file.read()
    try:
        rows = parse_ing_xls(content, session)
    except Exception as e:
        raise HTTPException(400, f"Error al procesar archivo: {e}")
    return rows


@router.post("/importar/confirmar", status_code=201)
def importar_confirmar(rows: list[ImportarRow], session: Session = Depends(get_session)):
    from app.modules.finanzas.models import Gasto
    from datetime import datetime, timezone
    saved = 0
    for row in rows:
        fecha = None
        if row.fecha:
            try:
                fecha = datetime.fromisoformat(row.fecha.replace("Z", "+00:00"))
                if fecha.tzinfo is None:
                    fecha = fecha.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        g = Gasto(
            cantidad=row.cantidad,
            categoria_id=row.categoria_id,
            descripcion=row.descripcion,
            fuente="importacion",
            **({"fecha": fecha} if fecha else {}),
        )
        session.add(g)
        saved += 1
    session.commit()
    return {"importados": saved}
