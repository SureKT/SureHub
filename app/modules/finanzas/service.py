from datetime import datetime, timezone
from sqlmodel import Session, select, func
from app.modules.finanzas.models import Gasto


def registrar_gasto(session: Session, descripcion: str, cantidad: float, categoria: str = None) -> Gasto:
    gasto = Gasto(descripcion=descripcion, cantidad=cantidad, categoria=categoria)
    session.add(gasto)
    session.commit()
    session.refresh(gasto)
    return gasto


def total_mes(session: Session) -> float:
    ahora = datetime.now(timezone.utc)
    inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = session.exec(
        select(func.sum(Gasto.cantidad)).where(Gasto.fecha >= inicio_mes)
    ).first()
    return result or 0.0


def ultimos_gastos(session: Session, n: int = 5) -> list[Gasto]:
    return list(session.exec(
        select(Gasto).order_by(Gasto.fecha.desc()).limit(n)
    ).all())


def gastos_por_categoria(session: Session) -> dict[str, float]:
    rows = session.exec(
        select(Gasto.categoria, func.sum(Gasto.cantidad))
        .group_by(Gasto.categoria)
    ).all()
    return {cat or "sin categoría": total for cat, total in rows}
