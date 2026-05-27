from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlmodel import Session
from app.database import get_session
from app.modules.finanzas.service import (
    create_category, list_categories, find_category,
    register_expense, get_expenses_filtered, month_summary, month_total,
    monthly_evolution, available_months
)

router = APIRouter(prefix="/api/finance", tags=["finance"])


class CategoryCreate(BaseModel):
    name: str
    type: str
    monthly_estimate: float = 0.0


class CategoryUpdate(BaseModel):
    monthly_estimate: float | None = None
    active: bool | None = None


class ExpenseCreate(BaseModel):
    category_id: int | None = None
    amount: float
    description: str | None = None
    date: str | None = None


class ExpenseUpdate(BaseModel):
    category_id: int | None = None
    amount: float | None = None
    description: str | None = None
    date: str | None = None


@router.get("/categories")
def get_categories(active_only: bool = Query(True), session: Session = Depends(get_session)):
    return list_categories(session, active_only=active_only)


@router.post("/categories", status_code=201)
def post_category(body: CategoryCreate, session: Session = Depends(get_session)):
    if find_category(session, body.name):
        raise HTTPException(400, "Category already exists")
    return create_category(session, body.name, body.type, body.monthly_estimate)


@router.patch("/categories/{id}")
def patch_category(id: int, body: CategoryUpdate, session: Session = Depends(get_session)):
    from app.modules.finanzas.models import Category
    cat = session.get(Category, id)
    if not cat:
        raise HTTPException(404)
    if body.monthly_estimate is not None:
        cat.monthly_estimate = body.monthly_estimate
    if body.active is not None:
        cat.active = body.active
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


@router.delete("/categories/{id}", status_code=204)
def delete_category(id: int, session: Session = Depends(get_session)):
    from app.modules.finanzas.models import Category
    cat = session.get(Category, id)
    if not cat:
        raise HTTPException(404)
    cat.active = False
    session.add(cat)
    session.commit()


@router.get("/expenses")
def get_expenses(
    year: int | None = Query(None),
    month: int | None = Query(None),
    category_id: int | None = Query(None),
    search: str | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=5000),
    order: str = Query("date"),
    asc: bool = Query(False),
    session: Session = Depends(get_session),
):
    expenses, total = get_expenses_filtered(session, year, month, category_id,
                                             search, from_date, to_date, page, per_page, order, asc)
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": e.id,
                "amount": e.amount,
                "description": e.description,
                "date": e.date,
                "source": e.source,
                "category": {"id": cat.id, "name": cat.name} if cat else None,
            }
            for e, cat in expenses
        ]
    }


@router.post("/expenses", status_code=201)
def post_expense(body: ExpenseCreate, session: Session = Depends(get_session)):
    if body.amount <= 0:
        raise HTTPException(400, "amount must be positive")
    from datetime import datetime, timezone
    date = None
    if body.date:
        try:
            date = datetime.fromisoformat(body.date).replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(400, "Invalid date format")
    from app.modules.finanzas.models import Expense
    expense = Expense(
        amount=body.amount,
        category_id=body.category_id,
        description=body.description,
        source="manual",
        **({"date": date} if date else {})
    )
    session.add(expense)
    session.commit()
    session.refresh(expense)
    return expense


@router.patch("/expenses/{id}")
def patch_expense(id: int, body: ExpenseUpdate, session: Session = Depends(get_session)):
    from app.modules.finanzas.models import Expense
    from datetime import datetime, timezone
    expense = session.get(Expense, id)
    if not expense:
        raise HTTPException(404)
    if body.amount is not None:
        expense.amount = body.amount
    if body.description is not None:
        expense.description = body.description
    if body.category_id is not None:
        expense.category_id = body.category_id
    if body.date is not None:
        try:
            expense.date = datetime.fromisoformat(body.date).replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(400, "Invalid date format")
    session.add(expense)
    session.commit()
    session.refresh(expense)
    return expense


@router.delete("/expenses/{id}", status_code=204)
def delete_expense(id: int, session: Session = Depends(get_session)):
    from app.modules.finanzas.models import Expense
    expense = session.get(Expense, id)
    if not expense:
        raise HTTPException(404)
    session.delete(expense)
    session.commit()


@router.get("/summary")
def get_summary(
    year: int | None = Query(None),
    month: int | None = Query(None),
    session: Session = Depends(get_session)
):
    return {
        "categories": month_summary(session, year, month),
        "total": month_total(session, year, month),
    }


@router.get("/evolution")
def get_evolution(months: int = Query(12, ge=2, le=24), session: Session = Depends(get_session)):
    return monthly_evolution(session, months)


@router.get("/months")
def get_months(session: Session = Depends(get_session)):
    return available_months(session)


class ImportRow(BaseModel):
    date: str | None = None
    description: str | None = None
    amount: float
    category_id: int | None = None


@router.post("/import/preview")
async def import_preview(file: UploadFile = File(...), session: Session = Depends(get_session)):
    from app.modules.finanzas.importer import parse_ing_xls
    content = await file.read()
    try:
        rows = parse_ing_xls(content, session)
    except Exception as e:
        raise HTTPException(400, f"Error processing file: {e}")
    return rows


@router.post("/import/confirm", status_code=201)
def import_confirm(rows: list[ImportRow], session: Session = Depends(get_session)):
    from app.modules.finanzas.models import Expense
    from datetime import datetime, timezone
    saved = 0
    for row in rows:
        date = None
        if row.date:
            try:
                date = datetime.fromisoformat(row.date.replace("Z", "+00:00"))
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        e = Expense(
            amount=row.amount,
            category_id=row.category_id,
            description=row.description,
            source="import",
            **({"date": date} if date else {}),
        )
        session.add(e)
        saved += 1
    session.commit()
    return {"imported": saved}
