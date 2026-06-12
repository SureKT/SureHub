from datetime import datetime, timezone

from app.modules.finanzas.models import Expense
from app.modules.finanzas.service import (
    available_months,
    create_category,
    create_recurring,
    find_category,
    generate_recurring,
    get_expenses_filtered,
    latest_expenses,
    list_categories,
    list_recurring,
    month_summary,
    month_total,
    month_total_by_category,
    monthly_evolution,
    register_expense,
)

YEAR, MONTH = 2026, 1  # fixed past month so summary fraction is 1.0


def _expense(session, amount, category_id=None, description=None, day=15):
    e = Expense(
        amount=amount,
        category_id=category_id,
        description=description,
        date=datetime(YEAR, MONTH, day, 12, 0, 0, tzinfo=timezone.utc),
    )
    session.add(e)
    session.commit()
    session.refresh(e)
    return e


class TestCategories:
    def test_create_category(self, session):
        cat = create_category(session, "Supermercado", "variable", 300.0)
        assert cat.id is not None
        assert cat.name == "Supermercado"
        assert cat.type == "variable"
        assert cat.monthly_estimate == 300.0
        assert cat.active is True

    def test_list_orders_by_type_then_name(self, session):
        create_category(session, "Ocio", "variable")
        create_category(session, "Alquiler", "fixed")
        create_category(session, "Gimnasio", "variable")
        names = [c.name for c in list_categories(session)]
        assert names == ["Alquiler", "Gimnasio", "Ocio"]

    def test_active_only_filter(self, session):
        active = create_category(session, "Activa", "variable")
        inactive = create_category(session, "Inactiva", "variable")
        inactive.active = False
        session.add(inactive)
        session.commit()

        assert [c.id for c in list_categories(session)] == [active.id]
        all_ids = {c.id for c in list_categories(session, active_only=False)}
        assert all_ids == {active.id, inactive.id}

    def test_find_category_case_insensitive(self, session):
        cat = create_category(session, "Supermercado", "variable")
        assert find_category(session, "supermercado").id == cat.id
        assert find_category(session, "SUPERMERCADO").id == cat.id
        assert find_category(session, "no existe") is None


class TestExpenses:
    def test_register_expense_defaults(self, session):
        cat = create_category(session, "Ocio", "variable")
        e = register_expense(session, 12.5, cat.id, "cine")
        assert e.id is not None
        assert e.amount == 12.5
        assert e.source == "telegram"
        assert e.date is not None

    def test_register_expense_without_category(self, session):
        e = register_expense(session, 9.99, source="manual")
        assert e.category_id is None
        assert e.source == "manual"

    def test_filter_by_year_month(self, session):
        _expense(session, 10)
        other = Expense(amount=99, date=datetime(2025, 12, 1, tzinfo=timezone.utc))
        session.add(other)
        session.commit()

        rows, total = get_expenses_filtered(session, year=YEAR, month=MONTH)
        assert total == 1
        assert rows[0][0].amount == 10

    def test_filter_by_year_only(self, session):
        _expense(session, 10)
        session.add(Expense(amount=99, date=datetime(2025, 12, 1, tzinfo=timezone.utc)))
        session.commit()

        _, total = get_expenses_filtered(session, year=YEAR)
        assert total == 1

    def test_filter_by_date_range(self, session):
        _expense(session, 10, day=5)
        _expense(session, 20, day=20)
        rows, total = get_expenses_filtered(
            session, from_str=f"{YEAR}-01-01", to_str=f"{YEAR}-01-10"
        )
        assert total == 1
        assert rows[0][0].amount == 10

    def test_filter_by_category(self, session):
        cat = create_category(session, "Ocio", "variable")
        _expense(session, 10, category_id=cat.id)
        _expense(session, 20)
        rows, total = get_expenses_filtered(session, category_id=cat.id)
        assert total == 1
        assert rows[0][1].name == "Ocio"

    def test_search_case_insensitive(self, session):
        _expense(session, 10, description="Cena Mercadona")
        _expense(session, 20, description="gasolina")
        rows, total = get_expenses_filtered(session, search="mercadona")
        assert total == 1
        assert rows[0][0].description == "Cena Mercadona"

    def test_pagination(self, session):
        for i in range(5):
            _expense(session, i + 1, day=i + 1)
        rows, total = get_expenses_filtered(session, page=2, per_page=2)
        assert total == 5
        assert len(rows) == 2

    def test_order_by_amount_asc(self, session):
        _expense(session, 30)
        _expense(session, 10)
        _expense(session, 20)
        rows, _ = get_expenses_filtered(session, order="amount", asc=True)
        assert [e.amount for e, _ in rows] == [10, 20, 30]

    def test_latest_expenses(self, session):
        cat = create_category(session, "Ocio", "variable")
        for day in (1, 2, 3):
            _expense(session, day, category_id=cat.id, day=day)
        latest = latest_expenses(session, n=2)
        assert len(latest) == 2
        assert latest[0][0].amount == 3  # most recent first
        assert latest[0][1].name == "Ocio"


class TestTotalsAndSummary:
    def test_month_total(self, session):
        _expense(session, 10)
        _expense(session, 15.5)
        assert month_total(session, YEAR, MONTH) == 25.5
        assert month_total(session, 2025, 6) == 0.0

    def test_month_total_by_category(self, session):
        cat = create_category(session, "Ocio", "variable")
        _expense(session, 10, category_id=cat.id)
        _expense(session, 99)
        assert month_total_by_category(session, cat.id, YEAR, MONTH) == 10

    def test_month_summary_totals_and_alert(self, session):
        ocio = create_category(session, "Ocio", "variable", estimate=50.0)
        alquiler = create_category(session, "Alquiler", "fixed", estimate=500.0)
        _expense(session, 60, category_id=ocio.id)
        _expense(session, 400, category_id=alquiler.id)

        summary = {r["name"]: r for r in month_summary(session, YEAR, MONTH)}
        assert summary["Ocio"]["total"] == 60
        assert summary["Ocio"]["alert"] is True
        # past month → fraction 1.0 → forecast equals the estimate
        assert summary["Ocio"]["forecast"] == 50.0
        assert summary["Alquiler"]["alert"] is False
        assert summary["Ocio"]["expense_count"] == 1

    def test_month_summary_excludes_inactive_categories(self, session):
        cat = create_category(session, "Vieja", "variable")
        cat.active = False
        session.add(cat)
        session.commit()
        assert month_summary(session, YEAR, MONTH) == []

    def test_monthly_evolution_length_and_labels(self, session):
        evolution = monthly_evolution(session, months=3)
        assert len(evolution) == 3
        now = datetime.now(timezone.utc)
        assert evolution[-1]["year"] == now.year
        assert evolution[-1]["month"] == now.month
        assert evolution[-1]["label"] == f"{now.month:02d}/{now.year}"

    def test_available_months(self, session):
        _expense(session, 10)
        session.add(Expense(amount=5, date=datetime(2025, 11, 3, tzinfo=timezone.utc)))
        session.commit()
        months = available_months(session)
        assert {"year": YEAR, "month": MONTH, "label": f"{MONTH:02d}/{YEAR}"} in months
        assert months[0]["year"] == YEAR  # descending order


class TestRecurring:
    def test_create_recurring(self, session):
        r = create_recurring(session, "Netflix", 12.99, day=5)
        assert r.id is not None
        assert r.active is True
        assert r.day == 5

    def test_generate_creates_expenses(self, session):
        cat = create_category(session, "Suscripciones", "fixed")
        create_recurring(session, "Netflix", 12.99, category_id=cat.id, day=5)

        result = generate_recurring(session, YEAR, MONTH)
        assert result["total"] == 1
        assert result["generated"] == [{"name": "Netflix", "amount": 12.99}]

        rows, total = get_expenses_filtered(session, year=YEAR, month=MONTH)
        assert total == 1
        expense = rows[0][0]
        assert expense.source == "recurring"
        assert expense.description == "Netflix"
        assert expense.date.day == 5

    def test_generate_is_idempotent(self, session):
        create_recurring(session, "Netflix", 12.99)
        generate_recurring(session, YEAR, MONTH)
        result = generate_recurring(session, YEAR, MONTH)
        assert result["total"] == 0
        assert result["skipped"] == ["Netflix"]
        _, total = get_expenses_filtered(session, year=YEAR, month=MONTH)
        assert total == 1

    def test_generate_skips_inactive(self, session):
        r = create_recurring(session, "Vieja", 5.0)
        r.active = False
        session.add(r)
        session.commit()
        result = generate_recurring(session, YEAR, MONTH)
        assert result["total"] == 0
        assert result["skipped"] == []

    def test_generate_clamps_day_to_month_length(self, session):
        create_recurring(session, "Fin de mes", 10.0, day=31)
        generate_recurring(session, 2026, 2)  # Feb 2026 has 28 days
        rows, _ = get_expenses_filtered(session, year=2026, month=2)
        assert rows[0][0].date.day == 28

    def test_list_recurring_generated_flag(self, session):
        create_recurring(session, "Netflix", 12.99, day=5)
        create_recurring(session, "Gym", 30.0, day=1)

        items = {r["name"]: r for r in list_recurring(session, YEAR, MONTH)}
        assert items["Netflix"]["generated_this_month"] is False

        generate_recurring(session, YEAR, MONTH)
        items = {r["name"]: r for r in list_recurring(session, YEAR, MONTH)}
        assert items["Netflix"]["generated_this_month"] is True
        assert items["Gym"]["generated_this_month"] is True
