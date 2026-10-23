import pytest

NOT_FOUND = {"error": "Expense not found"}


def create(client) -> int:
    response = client.post("/expenses", json={"title": "Taxi", "amount": 9, "category": "travel"})
    return response.json()["id"]


def test_deletes_existing_expense(db_client):
    expense_id = create(db_client)

    response = db_client.delete(f"/expenses/{expense_id}")

    assert response.status_code == 204
    assert response.content == b""
    assert db_client.get("/expenses").json()["total_count"] == 0


def test_deletes_only_the_requested_expense(db_client):
    keep, remove = create(db_client), create(db_client)

    db_client.delete(f"/expenses/{remove}")

    assert [item["id"] for item in db_client.get("/expenses").json()["items"]] == [keep]


def test_missing_expense_returns_404(db_client):
    response = db_client.delete("/expenses/999999")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_deleting_twice_returns_404_the_second_time(db_client):
    expense_id = create(db_client)
    db_client.delete(f"/expenses/{expense_id}")

    assert db_client.delete(f"/expenses/{expense_id}").status_code == 404


@pytest.mark.parametrize("bad_id", ["abc", "1.5", "-1", "0", "99999999999999999999"])
def test_ids_that_cannot_exist_return_404(client, bad_id):
    response = client.delete(f"/expenses/{bad_id}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
