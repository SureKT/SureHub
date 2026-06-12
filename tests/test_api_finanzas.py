from datetime import datetime, timezone

from app.modules.finanzas.models import Expense

YEAR, MONTH = 2026, 1


def _seed_expense(session, amount, category_id=None, description=None, day=15):
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


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


class TestCategoriesAPI:
    def test_create_and_list(self, client):
        r = client.post("/api/finance/categories",
                        json={"name": "Ocio", "type": "variable", "monthly_estimate": 50})
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "Ocio"
        assert body["active"] is True

        r = client.get("/api/finance/categories")
        assert r.status_code == 200
        assert [c["name"] for c in r.json()] == ["Ocio"]

    def test_duplicate_name_rejected(self, client):
        client.post("/api/finance/categories", json={"name": "Ocio", "type": "variable"})
        r = client.post("/api/finance/categories", json={"name": "ocio", "type": "variable"})
        assert r.status_code == 400

    def test_patch_estimate_and_active(self, client):
        cat_id = client.post("/api/finance/categories",
                             json={"name": "Ocio", "type": "variable"}).json()["id"]
        r = client.patch(f"/api/finance/categories/{cat_id}",
                         json={"monthly_estimate": 75, "active": False})
        assert r.status_code == 200
        assert r.json()["monthly_estimate"] == 75
        assert r.json()["active"] is False

    def test_patch_missing_404(self, client):
        assert client.patch("/api/finance/categories/999",
                            json={"monthly_estimate": 1}).status_code == 404

    def test_delete_is_soft(self, client):
        cat_id = client.post("/api/finance/categories",
                             json={"name": "Ocio", "type": "variable"}).json()["id"]
        assert client.delete(f"/api/finance/categories/{cat_id}").status_code == 204

        assert client.get("/api/finance/categories").json() == []
        all_cats = client.get("/api/finance/categories",
                              params={"active_only": False}).json()
        assert len(all_cats) == 1
        assert all_cats[0]["active"] is False

    def test_delete_missing_404(self, client):
        assert client.delete("/api/finance/categories/999").status_code == 404


class TestExpensesAPI:
    def test_create_expense(self, client):
        r = client.post("/api/finance/expenses",
                        json={"amount": 12.5, "description": "cine"})
        assert r.status_code == 201
        body = r.json()
        assert body["amount"] == 12.5
        assert body["source"] == "manual"

    def test_create_with_explicit_date(self, client):
        r = client.post("/api/finance/expenses",
                        json={"amount": 10, "date": "2026-01-15"})
        assert r.status_code == 201
        assert r.json()["date"].startswith("2026-01-15")

    def test_non_positive_amount_rejected(self, client):
        assert client.post("/api/finance/expenses",
                           json={"amount": 0}).status_code == 400
        assert client.post("/api/finance/expenses",
                           json={"amount": -5}).status_code == 400

    def test_invalid_date_rejected(self, client):
        r = client.post("/api/finance/expenses",
                        json={"amount": 10, "date": "no-es-fecha"})
        assert r.status_code == 400

    def test_list_with_filters(self, client, session):
        cat_id = client.post("/api/finance/categories",
                             json={"name": "Ocio", "type": "variable"}).json()["id"]
        _seed_expense(session, 10, category_id=cat_id, description="cine")
        _seed_expense(session, 20, description="otra cosa")

        r = client.get("/api/finance/expenses",
                       params={"year": YEAR, "month": MONTH})
        assert r.status_code == 200
        assert r.json()["total"] == 2

        r = client.get("/api/finance/expenses", params={"category_id": cat_id})
        assert r.json()["total"] == 1
        item = r.json()["items"][0]
        assert item["category"] == {"id": cat_id, "name": "Ocio"}

        r = client.get("/api/finance/expenses", params={"search": "CINE"})
        assert r.json()["total"] == 1

    def test_pagination_metadata(self, client, session):
        for i in range(3):
            _seed_expense(session, i + 1, day=i + 1)
        r = client.get("/api/finance/expenses",
                       params={"page": 2, "per_page": 2})
        body = r.json()
        assert body["total"] == 3
        assert body["page"] == 2
        assert len(body["items"]) == 1

    def test_patch_expense(self, client, session):
        e = _seed_expense(session, 10, description="antes")
        r = client.patch(f"/api/finance/expenses/{e.id}",
                         json={"amount": 99, "description": "después"})
        assert r.status_code == 200
        assert r.json()["amount"] == 99
        assert r.json()["description"] == "después"

    def test_patch_missing_404(self, client):
        assert client.patch("/api/finance/expenses/999",
                            json={"amount": 1}).status_code == 404

    def test_delete_expense(self, client, session):
        e = _seed_expense(session, 10)
        assert client.delete(f"/api/finance/expenses/{e.id}").status_code == 204
        assert client.get("/api/finance/expenses").json()["total"] == 0

    def test_delete_missing_404(self, client):
        assert client.delete("/api/finance/expenses/999").status_code == 404


class TestSummaryAPI:
    def test_summary_for_month(self, client, session):
        cat_id = client.post("/api/finance/categories",
                             json={"name": "Ocio", "type": "variable",
                                   "monthly_estimate": 50}).json()["id"]
        _seed_expense(session, 60, category_id=cat_id)

        r = client.get("/api/finance/summary",
                       params={"year": YEAR, "month": MONTH})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 60
        ocio = next(c for c in body["categories"] if c["name"] == "Ocio")
        assert ocio["total"] == 60
        assert ocio["alert"] is True

    def test_evolution(self, client):
        r = client.get("/api/finance/evolution", params={"months": 3})
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_evolution_validates_range(self, client):
        assert client.get("/api/finance/evolution",
                          params={"months": 1}).status_code == 422

    def test_months(self, client, session):
        _seed_expense(session, 10)
        r = client.get("/api/finance/months")
        assert r.status_code == 200
        assert {"year": YEAR, "month": MONTH, "label": f"{MONTH:02d}/{YEAR}"} in r.json()


class TestRecurringAPI:
    def test_create_and_list(self, client):
        r = client.post("/api/finance/recurring",
                        json={"name": "Netflix", "amount": 12.99, "day": 5})
        assert r.status_code == 201
        assert r.json()["name"] == "Netflix"

        r = client.get("/api/finance/recurring",
                       params={"year": YEAR, "month": MONTH})
        assert r.status_code == 200
        assert r.json()[0]["generated_this_month"] is False

    def test_day_out_of_range_rejected(self, client):
        assert client.post("/api/finance/recurring",
                           json={"name": "X", "amount": 1, "day": 0}).status_code == 400
        assert client.post("/api/finance/recurring",
                           json={"name": "X", "amount": 1, "day": 29}).status_code == 400

    def test_patch_recurring(self, client):
        rec_id = client.post("/api/finance/recurring",
                             json={"name": "Netflix", "amount": 12.99}).json()["id"]
        r = client.patch(f"/api/finance/recurring/{rec_id}",
                         json={"amount": 15.99, "active": False})
        assert r.status_code == 200
        assert r.json()["amount"] == 15.99
        assert r.json()["active"] is False

    def test_patch_invalid_day_rejected(self, client):
        rec_id = client.post("/api/finance/recurring",
                             json={"name": "Netflix", "amount": 12.99}).json()["id"]
        assert client.patch(f"/api/finance/recurring/{rec_id}",
                            json={"day": 30}).status_code == 400

    def test_delete_recurring(self, client):
        rec_id = client.post("/api/finance/recurring",
                             json={"name": "Netflix", "amount": 12.99}).json()["id"]
        assert client.delete(f"/api/finance/recurring/{rec_id}").status_code == 204
        assert client.get("/api/finance/recurring").json() == []

    def test_generate(self, client):
        client.post("/api/finance/recurring",
                    json={"name": "Netflix", "amount": 12.99, "day": 5})
        r = client.post("/api/finance/recurring/generate",
                        params={"year": YEAR, "month": MONTH})
        assert r.status_code == 201
        assert r.json()["total"] == 1

        r = client.post("/api/finance/recurring/generate",
                        params={"year": YEAR, "month": MONTH})
        assert r.json()["total"] == 0
        assert r.json()["skipped"] == ["Netflix"]
