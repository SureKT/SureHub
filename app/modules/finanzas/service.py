from calendar import monthrange
from datetime import datetime, timezone
from sqlmodel import Session, select, func
from app.modules.finanzas.models import Categoria, Gasto


# --- Categorias ---

def crear_categoria(session: Session, nombre: str, tipo: str, estimacion: float = 0.0) -> Categoria:
    cat = Categoria(nombre=nombre, tipo=tipo, estimacion_mensual=estimacion)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


def listar_categorias(session: Session) -> list[Categoria]:
    return list(session.exec(select(Categoria).order_by(Categoria.tipo, Categoria.nombre)).all())


def buscar_categoria(session: Session, nombre: str) -> Categoria | None:
    return session.exec(
        select(Categoria).where(func.lower(Categoria.nombre) == nombre.lower())
    ).first()


# --- Gastos ---

def registrar_gasto(session: Session, cantidad: float, categoria_id: int = None,
                    descripcion: str = None, fuente: str = "telegram") -> Gasto:
    gasto = Gasto(cantidad=cantidad, categoria_id=categoria_id,
                  descripcion=descripcion, fuente=fuente)
    session.add(gasto)
    session.commit()
    session.refresh(gasto)
    return gasto


def ultimos_gastos(session: Session, n: int = 5) -> list[tuple[Gasto, Categoria | None]]:
    gastos = list(session.exec(select(Gasto).order_by(Gasto.fecha.desc()).limit(n)).all())
    result = []
    for g in gastos:
        cat = session.get(Categoria, g.categoria_id) if g.categoria_id else None
        result.append((g, cat))
    return result


def total_mes_categoria(session: Session, categoria_id: int) -> float:
    ahora = datetime.now(timezone.utc)
    inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = session.exec(
        select(func.sum(Gasto.cantidad))
        .where(Gasto.categoria_id == categoria_id)
        .where(Gasto.fecha >= inicio_mes)
    ).first()
    return result or 0.0


def resumen_mes(session: Session) -> list[dict]:
    ahora = datetime.now(timezone.utc)
    dias_mes = monthrange(ahora.year, ahora.month)[1]
    fraccion = ahora.day / dias_mes

    categorias = listar_categorias(session)
    resultado = []
    for cat in categorias:
        total = total_mes_categoria(session, cat.id)
        prediccion = round(cat.estimacion_mensual * fraccion, 2)
        alerta = total > cat.estimacion_mensual and cat.estimacion_mensual > 0
        resultado.append({
            "id": cat.id,
            "nombre": cat.nombre,
            "tipo": cat.tipo,
            "estimacion": cat.estimacion_mensual,
            "prediccion": prediccion,
            "total": total,
            "alerta": alerta,
        })
    return resultado


def total_mes_global(session: Session) -> float:
    ahora = datetime.now(timezone.utc)
    inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = session.exec(
        select(func.sum(Gasto.cantidad)).where(Gasto.fecha >= inicio_mes)
    ).first()
    return result or 0.0
