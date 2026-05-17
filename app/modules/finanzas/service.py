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


def listar_categorias(session: Session, solo_activas: bool = True) -> list[Categoria]:
    q = select(Categoria)
    if solo_activas:
        q = q.where(Categoria.activa == True)  # noqa: E712
    return list(session.exec(q.order_by(Categoria.tipo, Categoria.nombre)).all())


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


def get_gastos_filtrados(session: Session, anio: int = None, mes: int = None,
                          categoria_id: int = None, busqueda: str = None,
                          page: int = 1, per_page: int = 50,
                          orden: str = "fecha", asc: bool = False
                          ) -> tuple[list[tuple[Gasto, Categoria | None]], int]:
    q = select(Gasto)

    if anio and mes:
        desde = datetime(anio, mes, 1, tzinfo=timezone.utc)
        dias = monthrange(anio, mes)[1]
        hasta = datetime(anio, mes, dias, 23, 59, 59, tzinfo=timezone.utc)
        q = q.where(Gasto.fecha >= desde).where(Gasto.fecha <= hasta)
    elif anio:
        desde = datetime(anio, 1, 1, tzinfo=timezone.utc)
        hasta = datetime(anio, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        q = q.where(Gasto.fecha >= desde).where(Gasto.fecha <= hasta)

    if categoria_id:
        q = q.where(Gasto.categoria_id == categoria_id)

    if busqueda:
        q = q.where(Gasto.descripcion.ilike(f"%{busqueda}%"))

    total = session.exec(select(func.count()).select_from(q.subquery())).first() or 0

    col = getattr(Gasto, orden, Gasto.fecha)
    q = q.order_by(col if asc else col.desc())
    q = q.offset((page - 1) * per_page).limit(per_page)

    gastos = list(session.exec(q).all())
    result = []
    for g in gastos:
        cat = session.get(Categoria, g.categoria_id) if g.categoria_id else None
        result.append((g, cat))
    return result, total


def ultimos_gastos(session: Session, n: int = 5) -> list[tuple[Gasto, Categoria | None]]:
    gastos = list(session.exec(select(Gasto).order_by(Gasto.fecha.desc()).limit(n)).all())
    result = []
    for g in gastos:
        cat = session.get(Categoria, g.categoria_id) if g.categoria_id else None
        result.append((g, cat))
    return result


def _inicio_fin_mes(anio: int, mes: int) -> tuple[datetime, datetime]:
    dias = monthrange(anio, mes)[1]
    return (
        datetime(anio, mes, 1, tzinfo=timezone.utc),
        datetime(anio, mes, dias, 23, 59, 59, tzinfo=timezone.utc),
    )


def total_mes_categoria(session: Session, categoria_id: int,
                         anio: int = None, mes: int = None) -> float:
    if not anio or not mes:
        ahora = datetime.now(timezone.utc)
        anio, mes = ahora.year, ahora.month
    desde, hasta = _inicio_fin_mes(anio, mes)
    result = session.exec(
        select(func.sum(Gasto.cantidad))
        .where(Gasto.categoria_id == categoria_id)
        .where(Gasto.fecha >= desde)
        .where(Gasto.fecha <= hasta)
    ).first()
    return result or 0.0


def resumen_mes(session: Session, anio: int = None, mes: int = None) -> list[dict]:
    ahora = datetime.now(timezone.utc)
    if not anio:
        anio = ahora.year
    if not mes:
        mes = ahora.month

    dias_mes = monthrange(anio, mes)[1]
    es_mes_actual = (anio == ahora.year and mes == ahora.month)
    fraccion = (ahora.day / dias_mes) if es_mes_actual else 1.0
    desde, hasta = _inicio_fin_mes(anio, mes)

    # Single query: sum + count grouped by category
    rows = session.exec(
        select(Gasto.categoria_id, func.sum(Gasto.cantidad), func.count(Gasto.id))
        .where(Gasto.fecha >= desde)
        .where(Gasto.fecha <= hasta)
        .group_by(Gasto.categoria_id)
    ).all()
    totals = {cat_id: (float(total or 0), int(count or 0)) for cat_id, total, count in rows}

    categorias = listar_categorias(session)
    resultado = []
    for cat in categorias:
        total, n_gastos = totals.get(cat.id, (0.0, 0))
        prediccion = round(cat.estimacion_mensual * fraccion, 2)
        alerta = total > cat.estimacion_mensual and cat.estimacion_mensual > 0
        resultado.append({
            "id": cat.id,
            "nombre": cat.nombre,
            "tipo": cat.tipo,
            "estimacion": cat.estimacion_mensual,
            "prediccion": prediccion,
            "total": total,
            "n_gastos": n_gastos,
            "alerta": alerta,
        })
    return resultado


def total_mes_global(session: Session, anio: int = None, mes: int = None) -> float:
    if not anio or not mes:
        ahora = datetime.now(timezone.utc)
        anio, mes = ahora.year, ahora.month
    desde, hasta = _inicio_fin_mes(anio, mes)
    result = session.exec(
        select(func.sum(Gasto.cantidad))
        .where(Gasto.fecha >= desde)
        .where(Gasto.fecha <= hasta)
    ).first()
    return result or 0.0


def evolucion_mensual(session: Session, meses: int = 12) -> list[dict]:
    ahora = datetime.now(timezone.utc)
    resultado = []
    for i in range(meses - 1, -1, -1):
        mes = ahora.month - i
        anio = ahora.year
        while mes <= 0:
            mes += 12
            anio -= 1
        total = total_mes_global(session, anio, mes)
        resultado.append({"anio": anio, "mes": mes, "total": total,
                           "label": f"{mes:02d}/{anio}"})
    return resultado


def meses_disponibles(session: Session) -> list[dict]:
    rows = session.exec(
        select(func.strftime('%Y', Gasto.fecha), func.strftime('%m', Gasto.fecha))
        .group_by(func.strftime('%Y', Gasto.fecha), func.strftime('%m', Gasto.fecha))
        .order_by(func.strftime('%Y', Gasto.fecha).desc(), func.strftime('%m', Gasto.fecha).desc())
    ).all()
    return [{"anio": int(a), "mes": int(m), "label": f"{int(m):02d}/{a}"} for a, m in rows]
