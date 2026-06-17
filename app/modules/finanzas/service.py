from calendar import monthrange
from datetime import datetime, timezone
from sqlmodel import Session, select, func
from app.modules.finanzas.models import Category, Expense, RecurringExpense


# --- Categories ---

def create_category(session: Session, name: str, type: str, estimate: float = 0.0) -> Category:
    cat = Category(name=name, type=type, monthly_estimate=estimate)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


def list_categories(session: Session, active_only: bool = True) -> list[Category]:
    q = select(Category)
    if active_only:
        q = q.where(Category.active == True)  # noqa: E712
    return list(session.exec(q.order_by(Category.type, Category.name)).all())


def find_category(session: Session, name: str) -> Category | None:
    return session.exec(
        select(Category).where(func.lower(Category.name) == name.lower())
    ).first()


# --- Expenses ---

def register_expense(session: Session, amount: float, category_id: int = None,
                     description: str = None, source: str = "telegram") -> Expense:
    expense = Expense(amount=amount, category_id=category_id,
                      description=description, source=source)
    session.add(expense)
    session.commit()
    session.refresh(expense)
    return expense


def get_expenses_filtered(session: Session, year: int = None, month: int = None,
                           category_id: int = None, search: str = None,
                           from_str: str = None, to_str: str = None,
                           page: int = 1, per_page: int = 50,
                           order: str = "date", asc: bool = False
                           ) -> tuple[list[tuple[Expense, Category | None]], int]:
    q = select(Expense)

    if from_str or to_str:
        if from_str:
            d = datetime.fromisoformat(from_str)
            q = q.where(Expense.date >= d.replace(tzinfo=timezone.utc))
        if to_str:
            h = datetime.fromisoformat(to_str).replace(hour=23, minute=59, second=59)
            q = q.where(Expense.date <= h.replace(tzinfo=timezone.utc))
    elif year and month:
        from_ = datetime(year, month, 1, tzinfo=timezone.utc)
        days = monthrange(year, month)[1]
        to = datetime(year, month, days, 23, 59, 59, tzinfo=timezone.utc)
        q = q.where(Expense.date >= from_).where(Expense.date <= to)
    elif year:
        from_ = datetime(year, 1, 1, tzinfo=timezone.utc)
        to = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        q = q.where(Expense.date >= from_).where(Expense.date <= to)

    if category_id:
        q = q.where(Expense.category_id == category_id)

    if search:
        q = q.where(Expense.description.ilike(f"%{search}%"))

    total = session.exec(select(func.count()).select_from(q.subquery())).first() or 0

    col = getattr(Expense, order, Expense.date)
    q = q.order_by(col if asc else col.desc())
    q = q.offset((page - 1) * per_page).limit(per_page)

    expenses = list(session.exec(q).all())
    result = []
    for e in expenses:
        cat = session.get(Category, e.category_id) if e.category_id else None
        result.append((e, cat))
    return result, total


def latest_expenses(session: Session, n: int = 5) -> list[tuple[Expense, Category | None]]:
    expenses = list(session.exec(select(Expense).order_by(Expense.date.desc()).limit(n)).all())
    result = []
    for e in expenses:
        cat = session.get(Category, e.category_id) if e.category_id else None
        result.append((e, cat))
    return result


def _month_range(year: int, month: int) -> tuple[datetime, datetime]:
    # Límites naive: las fechas se guardan como texto naive en SQLite ("YYYY-MM-DD
    # HH:MM:SS"). Con tzinfo, el bind serializa "...+00:00" y la comparación de texto
    # excluía los gastos del día 1 a medianoche (ej. Spotify recurrente). Naive compara
    # bien tanto con filas naive (csv/import) como tz-aware (bot, llevan offset y hora real).
    days = monthrange(year, month)[1]
    return (
        datetime(year, month, 1),
        datetime(year, month, days, 23, 59, 59),
    )


def month_total_by_category(session: Session, category_id: int,
                             year: int = None, month: int = None) -> float:
    if not year or not month:
        now = datetime.now(timezone.utc)
        year, month = now.year, now.month
    from_, to = _month_range(year, month)
    result = session.exec(
        select(func.sum(Expense.amount))
        .where(Expense.category_id == category_id)
        .where(Expense.date >= from_)
        .where(Expense.date <= to)
    ).first()
    return result or 0.0


def month_summary(session: Session, year: int = None, month: int = None) -> list[dict]:
    now = datetime.now(timezone.utc)
    if not year:
        year = now.year
    if not month:
        month = now.month

    days_in_month = monthrange(year, month)[1]
    is_current = (year == now.year and month == now.month)
    fraction = (now.day / days_in_month) if is_current else 1.0
    from_, to = _month_range(year, month)

    rows = session.exec(
        select(Expense.category_id, func.sum(Expense.amount), func.count(Expense.id))
        .where(Expense.date >= from_)
        .where(Expense.date <= to)
        .group_by(Expense.category_id)
    ).all()
    totals = {cat_id: (float(total or 0), int(count or 0)) for cat_id, total, count in rows}

    categories = list_categories(session)
    result = []
    for cat in categories:
        total, n_expenses = totals.get(cat.id, (0.0, 0))
        forecast = round(cat.monthly_estimate * fraction, 2)
        alert = total > cat.monthly_estimate and cat.monthly_estimate > 0
        result.append({
            "id": cat.id,
            "name": cat.name,
            "type": cat.type,
            "estimate": cat.monthly_estimate,
            "forecast": forecast,
            "total": total,
            "expense_count": n_expenses,
            "alert": alert,
        })
    return result


def month_total(session: Session, year: int = None, month: int = None) -> float:
    if not year or not month:
        now = datetime.now(timezone.utc)
        year, month = now.year, now.month
    from_, to = _month_range(year, month)
    result = session.exec(
        select(func.sum(Expense.amount))
        .where(Expense.date >= from_)
        .where(Expense.date <= to)
    ).first()
    return result or 0.0


def monthly_evolution(session: Session, months: int = 12) -> list[dict]:
    now = datetime.now(timezone.utc)
    result = []
    for i in range(months - 1, -1, -1):
        month = now.month - i
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        total = month_total(session, year, month)
        result.append({"year": year, "month": month, "total": total,
                        "label": f"{month:02d}/{year}"})
    return result


def available_months(session: Session) -> list[dict]:
    rows = session.exec(
        select(func.strftime('%Y', Expense.date), func.strftime('%m', Expense.date))
        .group_by(func.strftime('%Y', Expense.date), func.strftime('%m', Expense.date))
        .order_by(func.strftime('%Y', Expense.date).desc(), func.strftime('%m', Expense.date).desc())
    ).all()
    return [{"year": int(y), "month": int(m), "label": f"{int(m):02d}/{y}"} for y, m in rows]


# --- Recurring ---

def list_recurring(session: Session, year: int = None, month: int = None) -> list[dict]:
    now = datetime.now(timezone.utc)
    if not year:
        year = now.year
    if not month:
        month = now.month
    from_, to = _month_range(year, month)

    recurring = list(session.exec(
        select(RecurringExpense).order_by(RecurringExpense.day, RecurringExpense.name)
    ).all())

    generated_ids = {
        e.recurring_id
        for e in session.exec(
            select(Expense)
            .where(Expense.recurring_id.is_not(None))
            .where(Expense.date >= from_)
            .where(Expense.date <= to)
        ).all()
    }

    result = []
    for r in recurring:
        cat = session.get(Category, r.category_id) if r.category_id else None
        result.append({
            "id": r.id,
            "name": r.name,
            "amount": r.amount,
            "category_id": r.category_id,
            "category_name": cat.name if cat else None,
            "day": r.day,
            "active": r.active,
            "generated_this_month": r.id in generated_ids,
        })
    return result


def create_recurring(session: Session, name: str, amount: float,
                     category_id: int = None, day: int = 1) -> RecurringExpense:
    r = RecurringExpense(name=name, amount=amount, category_id=category_id, day=day)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


def generate_recurring(session: Session, year: int = None, month: int = None) -> dict:
    now = datetime.now(timezone.utc)
    if not year:
        year = now.year
    if not month:
        month = now.month
    from_, to = _month_range(year, month)

    recurring = list(session.exec(
        select(RecurringExpense).where(RecurringExpense.active == True)  # noqa: E712
    ).all())

    generated_ids = {
        e.recurring_id
        for e in session.exec(
            select(Expense)
            .where(Expense.recurring_id.is_not(None))
            .where(Expense.date >= from_)
            .where(Expense.date <= to)
        ).all()
    }

    generated, skipped = [], []
    for r in recurring:
        if r.id in generated_ids:
            skipped.append(r.name)
            continue
        day_real = min(r.day, monthrange(year, month)[1])
        e = Expense(
            amount=r.amount,
            category_id=r.category_id,
            description=r.name,
            source="recurring",
            recurring_id=r.id,
            date=datetime(year, month, day_real, 8, 0, 0, tzinfo=timezone.utc),
        )
        session.add(e)
        generated.append({"name": r.name, "amount": r.amount})

    session.commit()
    return {"generated": generated, "skipped": skipped, "total": len(generated)}
