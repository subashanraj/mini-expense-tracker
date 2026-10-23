import pytest

ZEROS = {"food": 0, "travel": 0, "bills": 0, "other": 0}


def add(client, amount, category, date):
    response = client.post(
        "/expenses", json={"title": "x", "amount": amount, "category": category, "date": date}
    )
    assert response.status_code == 201


def test_totals_per_category_for_the_month(db_client):
    add(db_client, "10.10", "food", "2026-10-01")  # first day of month
    add(db_client, "5.20", "food", "2026-10-15")
    add(db_client, "100", "bills", "2026-10-10")
    add(db_client, "999", "food", "2026-09-30")  # previous month: excluded

    response = db_client.get("/expenses/summary?month=2026-10")

    assert response.status_code == 200
    assert response.json() == {
        "month": "2026-10",
        "totals": {"food": 15.3, "travel": 0, "bills": 100, "other": 0},
        "total": 115.3,
    }


def test_last_day_of_month_is_included_and_next_month_excluded(db_client):
    add(db_client, "7", "other", "2026-09-30")
    add(db_client, "50", "other", "2026-10-01")

    assert db_client.get("/expenses/summary?month=2026-09").json()["totals"]["other"] == 7


def test_december_rolls_over_to_next_year(db_client):
    add(db_client, "8", "travel", "2025-12-31")
    add(db_client, "3", "travel", "2026-01-01")

    assert db_client.get("/expenses/summary?month=2025-12").json()["totals"]["travel"] == 8


def test_month_without_expenses_returns_zeros(db_client):
    assert db_client.get("/expenses/summary?month=2026-01").json() == {
        "month": "2026-01",
        "totals": ZEROS,
        "total": 0,
    }


@pytest.mark.parametrize(
    "query, message",
    [
        ("", "month is required (YYYY-MM)"),
        ("?month=", "month is required (YYYY-MM)"),
        ("?month=2026-13", "month must be in YYYY-MM format"),
        ("?month=2026-00", "month must be in YYYY-MM format"),
        ("?month=2026-1", "month must be in YYYY-MM format"),
        ("?month=2026-10-01", "month must be in YYYY-MM format"),
        ("?month=october", "month must be in YYYY-MM format"),
    ],
)
def test_rejects_invalid_month(client, query, message):
    response = client.get(f"/expenses/summary{query}")

    assert response.status_code == 400
    assert response.json() == {"error": message}
