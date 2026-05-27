from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session
from app.database import get_session
from app.modules.diario.service import (
    list_collections, create_collection, delete_collection,
    list_fields, create_field, update_field, delete_field,
    list_entries, get_entry, create_entry, update_entry, delete_entry,
)

router = APIRouter(prefix="/api/diary", tags=["diary"])


# --- Collections ---

class CollectionCreate(BaseModel):
    name: str
    type: str = "journal"


@router.get("/collections")
def get_collections(session: Session = Depends(get_session)):
    return list_collections(session)


@router.post("/collections", status_code=201)
def post_collection(body: CollectionCreate, session: Session = Depends(get_session)):
    return create_collection(session, body.name, body.type)


@router.delete("/collections/{id}", status_code=204)
def del_collection(id: int, session: Session = Depends(get_session)):
    delete_collection(session, id)


# --- Metric fields ---

class FieldCreate(BaseModel):
    name: str
    field_type: str = "number"
    order: int = 0


class FieldUpdate(BaseModel):
    name: str | None = None
    field_type: str | None = None
    active: bool | None = None
    order: int | None = None


@router.get("/fields")
def get_fields(active_only: bool = Query(False), session: Session = Depends(get_session)):
    return list_fields(session, active_only=active_only)


@router.post("/fields", status_code=201)
def post_field(body: FieldCreate, session: Session = Depends(get_session)):
    return create_field(session, body.name, body.field_type, body.order)


@router.patch("/fields/{id}")
def patch_field(id: int, body: FieldUpdate, session: Session = Depends(get_session)):
    f = update_field(session, id, **body.model_dump(exclude_none=True))
    if not f:
        raise HTTPException(404)
    return f


@router.delete("/fields/{id}", status_code=204)
def del_field(id: int, session: Session = Depends(get_session)):
    delete_field(session, id)


# --- Entries ---

class MetricIn(BaseModel):
    field_id: int
    value: str


class EntryCreate(BaseModel):
    date: str | None = None
    title: str | None = None
    text: str | None = None
    collection_id: int | None = None
    metrics: list[MetricIn] = []


class EntryUpdate(BaseModel):
    date: str | None = None
    title: str | None = None
    text: str | None = None
    collection_id: int | None = None
    metrics: list[MetricIn] | None = None


@router.get("/entries")
def get_entries(
    collection_id: int | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    items, total = list_entries(session, collection_id, from_date, to_date, page, per_page)
    return {"total": total, "page": page, "per_page": per_page, "items": items}


@router.get("/entries/{id}")
def get_entry_route(id: int, session: Session = Depends(get_session)):
    e = get_entry(session, id)
    if not e:
        raise HTTPException(404)
    return e


@router.post("/entries", status_code=201)
def post_entry(body: EntryCreate, session: Session = Depends(get_session)):
    date = None
    if body.date:
        try:
            date = datetime.fromisoformat(body.date.replace("Z", "+00:00"))
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(400, "Invalid date format")
    return create_entry(
        session, date=date, title=body.title, text=body.text,
        collection_id=body.collection_id,
        metrics=[m.model_dump() for m in body.metrics],
    )


@router.patch("/entries/{id}")
def patch_entry(id: int, body: EntryUpdate, session: Session = Depends(get_session)):
    kwargs = body.model_dump(exclude_none=True)
    if "date" in kwargs:
        try:
            d = datetime.fromisoformat(kwargs["date"].replace("Z", "+00:00"))
            kwargs["date"] = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(400, "Invalid date format")
    if "metrics" in kwargs:
        kwargs["metrics"] = [m for m in kwargs["metrics"]]
    e = update_entry(session, id, **kwargs)
    if not e:
        raise HTTPException(404)
    return e


@router.delete("/entries/{id}", status_code=204)
def del_entry(id: int, session: Session = Depends(get_session)):
    delete_entry(session, id)
