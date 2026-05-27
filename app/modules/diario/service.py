from datetime import datetime, timezone
from sqlmodel import Session, select
from app.modules.diario.models import DiaryEntry, DiaryCollection, MetricField, MetricLog


# --- Collections ---

def list_collections(session: Session) -> list[DiaryCollection]:
    return list(session.exec(select(DiaryCollection).order_by(DiaryCollection.name)).all())


def create_collection(session: Session, name: str, type: str = "journal") -> DiaryCollection:
    c = DiaryCollection(name=name, type=type)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def delete_collection(session: Session, id: int) -> None:
    c = session.get(DiaryCollection, id)
    if c:
        session.delete(c)
        session.commit()


# --- Metric fields ---

def list_fields(session: Session, active_only: bool = False) -> list[MetricField]:
    q = select(MetricField)
    if active_only:
        q = q.where(MetricField.active == True)  # noqa: E712
    return list(session.exec(q.order_by(MetricField.order, MetricField.name)).all())


def create_field(session: Session, name: str, field_type: str = "number", order: int = 0) -> MetricField:
    f = MetricField(name=name, field_type=field_type, order=order)
    session.add(f)
    session.commit()
    session.refresh(f)
    return f


def update_field(session: Session, id: int, **kwargs) -> MetricField | None:
    f = session.get(MetricField, id)
    if not f:
        return None
    for k, v in kwargs.items():
        if v is not None:
            setattr(f, k, v)
    session.add(f)
    session.commit()
    session.refresh(f)
    return f


def delete_field(session: Session, id: int) -> None:
    f = session.get(MetricField, id)
    if f:
        session.delete(f)
        session.commit()


# --- Entries ---

def list_entries(session: Session, collection_id: int = None,
                 from_date: str = None, to_date: str = None,
                 page: int = 1, per_page: int = 50) -> tuple[list[dict], int]:
    q = select(DiaryEntry)
    if collection_id:
        q = q.where(DiaryEntry.collection_id == collection_id)
    if from_date:
        d = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc)
        q = q.where(DiaryEntry.date >= d)
    if to_date:
        d = datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc)
        q = q.where(DiaryEntry.date <= d)

    from sqlmodel import func
    total = session.exec(select(func.count()).select_from(q.subquery())).first() or 0
    q = q.order_by(DiaryEntry.date.desc()).offset((page - 1) * per_page).limit(per_page)
    entries = list(session.exec(q).all())
    return [_entry_dict(session, e) for e in entries], total


def get_entry(session: Session, id: int) -> dict | None:
    e = session.get(DiaryEntry, id)
    if not e:
        return None
    return _entry_dict(session, e)


def create_entry(session: Session, date: datetime = None, title: str = None,
                 text: str = None, collection_id: int = None,
                 metrics: list[dict] = None) -> dict:
    e = DiaryEntry(
        date=date or datetime.now(timezone.utc),
        title=title,
        text=text,
        collection_id=collection_id,
    )
    session.add(e)
    session.commit()
    session.refresh(e)
    if metrics:
        _save_metrics(session, e.id, metrics)
    return _entry_dict(session, e)


def update_entry(session: Session, id: int, **kwargs) -> dict | None:
    e = session.get(DiaryEntry, id)
    if not e:
        return None
    metrics = kwargs.pop("metrics", None)
    for k, v in kwargs.items():
        setattr(e, k, v)
    session.add(e)
    session.commit()
    session.refresh(e)
    if metrics is not None:
        # Replace all metric logs for this entry
        existing = list(session.exec(select(MetricLog).where(MetricLog.entry_id == id)).all())
        for m in existing:
            session.delete(m)
        session.commit()
        _save_metrics(session, id, metrics)
    return _entry_dict(session, e)


def delete_entry(session: Session, id: int) -> None:
    e = session.get(DiaryEntry, id)
    if e:
        logs = list(session.exec(select(MetricLog).where(MetricLog.entry_id == id)).all())
        for m in logs:
            session.delete(m)
        session.delete(e)
        session.commit()


def _save_metrics(session: Session, entry_id: int, metrics: list[dict]) -> None:
    for m in metrics:
        if m.get("value") not in (None, ""):
            log = MetricLog(entry_id=entry_id, field_id=m["field_id"], value=str(m["value"]))
            session.add(log)
    session.commit()


def _entry_dict(session: Session, e: DiaryEntry) -> dict:
    logs = list(session.exec(select(MetricLog).where(MetricLog.entry_id == e.id)).all())
    col = session.get(DiaryCollection, e.collection_id) if e.collection_id else None
    return {
        "id": e.id,
        "date": e.date,
        "title": e.title,
        "text": e.text,
        "collection_id": e.collection_id,
        "collection_name": col.name if col else None,
        "collection_type": col.type if col else None,
        "metrics": [{"id": m.id, "field_id": m.field_id, "value": m.value} for m in logs],
        "created_at": e.created_at,
    }
