import pytest
from sqlalchemy import func, select

from app.models import Expense

VALID = {"title": "Lunch", "amount": 12.5, "category": "food", "date": "2026-10-14"}


def post(client, **overrides):
    body = {**VALID, **overrides}
    return client.post("/expenses", json={k: v for k, v in body.items() if v is not ...})


def count_rows(db) -> int:
    with db() as session:
        return session.scalar(select(func.count()).select_from(Expense))


# --- Success -----------------------------------------------------------------


def test_creates_expense_and_returns_201(db_client, db):
    response = post(db_client)

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    assert body["title"] == "Lunch"
    assert body["amount"] == 12.5
    assert body["category"] == "food"
    assert body["date"] == "2026-10-14"
    assert "created_at" in body
    assert count_rows(db) == 1


def test_date_defaults_to_today_when_omitted(db_client):
    response = post(db_client, date=...)

    assert response.status_code == 201
    assert response.json()["date"] == "2026-10-15"


def test_today_is_allowed(db_client):
    assert post(db_client, date="2026-10-15").status_code == 201


def test_title_is_trimmed(db_client):
    assert post(db_client, title="  Taxi  ").json()["title"] == "Taxi"


def test_title_of_exactly_100_characters_is_allowed(db_client):
    assert post(db_client, title="a" * 100).status_code == 201


@pytest.mark.parametrize("amount, stored", [("12.50", 12.5), (0.01, 0.01), (99999999.99, 99999999.99), (7, 7)])
def test_accepts_valid_amounts(db_client, amount, stored):
    response = post(db_client, amount=amount)

    assert response.status_code == 201
    assert response.json()["amount"] == stored


# --- Validation (rejected before touching the database) ----------------------


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"title": ...}, "title is required"),
        ({"title": None}, "title is required"),
        ({"title": "   "}, "title is required"),
        ({"title": "a" * 101}, "title must be at most 100 characters"),
        ({"title": 123}, "title must be a string"),
        ({"amount": ...}, "amount is required"),
        ({"amount": 0}, "amount must be greater than 0"),
        ({"amount": -5}, "amount must be greater than 0"),
        ({"amount": "abc"}, "amount must be a number"),
        ({"amount": ""}, "amount must be a number"),
        ({"amount": True}, "amount must be a number"),
        ({"amount": "NaN"}, "amount must be a number"),
        ({"amount": "Infinity"}, "amount must be a number"),
        ({"amount": [5]}, "amount must be a number"),
        ({"amount": 1.005}, "amount must have at most 2 decimal places"),
        ({"amount": "10.999"}, "amount must have at most 2 decimal places"),
        ({"amount": 100000000}, "amount must be at most 99999999.99"),
        ({"category": ...}, "category is required"),
        ({"category": "shopping"}, "category must be one of: food, travel, bills, other"),
        ({"category": "FOOD"}, "category must be one of: food, travel, bills, other"),
        ({"date": "15-10-2026"}, "date must be in YYYY-MM-DD format"),
        ({"date": "2026-10-1"}, "date must be in YYYY-MM-DD format"),
        ({"date": 20261015}, "date must be in YYYY-MM-DD format"),
        ({"date": "2026-02-30"}, "date must be a valid calendar date"),
        ({"date": "2026-10-16"}, "date cannot be in the future"),
    ],
)
def test_rejects_invalid_input_with_400(client, overrides, message):
    response = post(client, **overrides)

    assert response.status_code == 400
    assert response.json() == {"error": message}


def test_reports_first_invalid_field_when_several_are_wrong(client):
    response = client.post("/expenses", json={"title": "", "amount": -1})

    assert response.json() == {"error": "title is required"}


def test_rejects_malformed_json(client):
    response = client.post(
        "/expenses", content="{not json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 400
    assert response.json() == {"error": "Request body must be valid JSON"}


@pytest.mark.parametrize("body", [[1, 2], "text", 5])
def test_rejects_non_object_body(client, body):
    response = client.post("/expenses", json=body)

    assert response.status_code == 400
    assert response.json() == {"error": "Request body must be a JSON object"}


def test_invalid_input_is_not_saved(db_client, db):
    post(db_client, amount=0)

    assert count_rows(db) == 0
