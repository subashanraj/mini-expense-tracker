import datetime as dt
from decimal import Decimal

import pytest

from app.models import Expense


@pytest.fixture
def seed(db):
    """Insert rows directly. Each row: (title, amount, category, date[, created_at])."""

    def insert(*rows):
        base = dt.datetime(2026, 10, 1, tzinfo=dt.UTC)
        with db() as session:
            session.add_all(
                Expense(
                    title=row[0],
                    amount=Decimal(row[1]),
                    category=row[2],
                    expense_date=dt.date.fromisoformat(row[3]),
                    # Distinct, increasing created_at so tie-breaking is deterministic.
                    created_at=row[4] if len(row) > 4 else base + dt.timedelta(minutes=i),
                )
                for i, row in enumerate(rows)
            )
            session.commit()

    return insert


def titles(response) -> list[str]:
    return [item["title"] for item in response.json()["items"]]


# --- Shape and ordering -------------------------------------------------------


def test_empty_list(db_client):
    response = db_client.get("/expenses")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total_count": 0, "total_amount": 0}


def test_item_shape(db_client, seed):
    seed(("Lunch", "12.50", "food", "2026-10-10"))

    item = db_client.get("/expenses").json()["items"][0]

    assert set(item) == {"id", "title", "amount", "category", "date", "created_at"}
    assert item["amount"] == 12.5
    assert item["date"] == "2026-10-10"


def test_newest_date_first(db_client, seed):
    seed(("old", "1", "food", "2026-09-01"), ("new", "1", "food", "2026-10-10"), ("mid", "1", "food", "2026-10-01"))

    assert titles(db_client.get("/expenses")) == ["new", "mid", "old"]


def test_same_date_ordered_by_most_recently_created(db_client, seed):
    seed(("first", "1", "food", "2026-10-10"), ("second", "1", "food", "2026-10-10"))

    assert titles(db_client.get("/expenses")) == ["second", "first"]


# --- Pagination -----------------------------------------------------------------


def seed_twelve(seed):
    # e01 is oldest, e12 newest; amounts 1..12 (sum 78).
    seed(*[(f"e{i:02}", str(i), "food", f"2026-10-{i:02}") for i in range(1, 13)])


def test_default_limit_is_10(db_client, seed):
    seed_twelve(seed)

    body = db_client.get("/expenses").json()

    assert len(body["items"]) == 10
    assert body["items"][0]["title"] == "e12"
    assert body["total_count"] == 12


def test_second_page_has_the_rest_without_overlap(db_client, seed):
    seed_twelve(seed)

    first = titles(db_client.get("/expenses?page=1"))
    second = titles(db_client.get("/expenses?page=2"))

    assert second == ["e02", "e01"]
    assert not set(first) & set(second)


def test_custom_limit(db_client, seed):
    seed_twelve(seed)

    assert titles(db_client.get("/expenses?limit=3&page=2")) == ["e09", "e08", "e07"]


def test_page_past_the_end_is_empty_but_keeps_totals(db_client, seed):
    seed_twelve(seed)

    body = db_client.get("/expenses?page=99").json()

    assert body == {"items": [], "total_count": 12, "total_amount": 78}


def test_totals_cover_all_matching_rows_not_just_the_page(db_client, seed):
    seed_twelve(seed)

    body = db_client.get("/expenses?limit=5").json()

    assert len(body["items"]) == 5
    assert body["total_count"] == 12
    assert body["total_amount"] == 78  # not 12+11+10+9+8 = 50


def test_total_amount_is_exact_decimal(db_client, seed):
    seed(("a", "0.10", "food", "2026-10-01"), ("b", "0.20", "food", "2026-10-02"))

    assert db_client.get("/expenses").json()["total_amount"] == 0.3  # float math would give 0.30000000000000004


# --- Filters --------------------------------------------------------------------


@pytest.fixture
def mixed(seed):
    seed(
        ("groceries", "40.00", "food", "2026-09-30"),
        ("train", "15.50", "travel", "2026-10-01"),
        ("dinner", "25.25", "food", "2026-10-05"),
        ("power", "100.00", "bills", "2026-10-10"),
        ("snack", "4.75", "food", "2026-10-15"),
    )


def test_category_filter(db_client, mixed):
    body = db_client.get("/expenses?category=food").json()

    assert titles_of(body) == ["snack", "dinner", "groceries"]
    assert body["total_count"] == 3
    assert body["total_amount"] == 70


def test_date_range_is_inclusive(db_client, mixed):
    body = db_client.get("/expenses?from=2026-10-01&to=2026-10-10").json()

    assert titles_of(body) == ["power", "dinner", "train"]
    assert body["total_amount"] == 140.75


def test_from_only(db_client, mixed):
    assert titles_of(db_client.get("/expenses?from=2026-10-10").json()) == ["snack", "power"]


def test_to_only(db_client, mixed):
    assert titles_of(db_client.get("/expenses?to=2026-09-30").json()) == ["groceries"]


def test_category_and_dates_combine(db_client, mixed):
    body = db_client.get("/expenses?category=food&from=2026-10-01").json()

    assert titles_of(body) == ["snack", "dinner"]
    assert body["total_count"] == 2
    assert body["total_amount"] == 30


def test_filter_with_no_matches(db_client, mixed):
    assert db_client.get("/expenses?category=other").json() == {
        "items": [],
        "total_count": 0,
        "total_amount": 0,
    }


def test_empty_filter_values_are_ignored(db_client, mixed):
    assert db_client.get("/expenses?category=&from=&to=").json()["total_count"] == 5


def titles_of(body) -> list[str]:
    return [item["title"] for item in body["items"]]


# --- Invalid parameters ---------------------------------------------------------

CATEGORY_ERROR = "category must be one of: food, travel, bills, other"
PAGE_ERROR = "page must be an integer between 1 and 1000000"
LIMIT_ERROR = "limit must be an integer between 1 and 100"


@pytest.mark.parametrize(
    "query, message",
    [
        ("category=shopping", CATEGORY_ERROR),
        ("category=Food", CATEGORY_ERROR),
        ("from=2026/10/01", "from must be in YYYY-MM-DD format"),
        ("from=yesterday", "from must be in YYYY-MM-DD format"),
        ("to=2026-13-01", "to must be a valid calendar date"),
        ("from=2026-10-10&to=2026-10-01", "from must be on or before to"),
        ("page=0", PAGE_ERROR),
        ("page=-1", PAGE_ERROR),
        ("page=abc", PAGE_ERROR),
        ("page=1.5", PAGE_ERROR),
        ("page=1000001", PAGE_ERROR),
        ("limit=0", LIMIT_ERROR),
        ("limit=101", LIMIT_ERROR),
        ("limit=ten", LIMIT_ERROR),
    ],
)
def test_rejects_invalid_query_parameters(client, query, message):
    response = client.get(f"/expenses?{query}")

    assert response.status_code == 400
    assert response.json() == {"error": message}
