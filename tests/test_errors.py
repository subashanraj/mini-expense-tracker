"""Every failure path returns {"error": "..."} and never leaks internals."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import get_session
from app.errors import DATABASE_ERROR, INTERNAL_ERROR
from app.main import app
from app.routes import get_today
from tests.conftest import TODAY

SECRET = "password=hunter2 host=db.internal"


class FailingSession:
    """Stands in for a Session whose every call fails like a dropped connection."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def __getattr__(self, _name):
        def fail(*_args, **_kwargs):
            raise self.error

        return fail


@pytest.fixture
def failing_client():
    def make(error: Exception) -> TestClient:
        app.dependency_overrides[get_today] = lambda: TODAY
        app.dependency_overrides[get_session] = lambda: FailingSession(error)
        # Let the app's own 500 handler answer instead of re-raising into the test.
        return TestClient(app, raise_server_exceptions=False)

    yield make
    app.dependency_overrides.clear()


VALID = {"title": "Lunch", "amount": 10, "category": "food"}
DATABASE_CALLS = [
    ("post", "/expenses", {"json": VALID}),
    ("get", "/expenses", {}),
    ("delete", "/expenses/1", {}),
    ("get", "/expenses/summary?month=2026-10", {}),
]


@pytest.mark.parametrize("method, url, kwargs", DATABASE_CALLS)
def test_database_failure_returns_generic_500(failing_client, method, url, kwargs):
    client = failing_client(OperationalError("SELECT * FROM expenses", {}, Exception(SECRET)))

    response = getattr(client, method)(url, **kwargs)

    assert response.status_code == 500
    assert response.json() == {"error": DATABASE_ERROR}
    assert "hunter2" not in response.text
    assert "SELECT" not in response.text


def test_unexpected_exception_returns_generic_500(failing_client):
    client = failing_client(RuntimeError(SECRET))

    response = client.get("/expenses")

    assert response.status_code == 500
    assert response.json() == {"error": INTERNAL_ERROR}


def test_validation_runs_before_the_database(failing_client):
    client = failing_client(OperationalError("x", {}, Exception("db down")))

    assert client.post("/expenses", json={**VALID, "amount": 0}).status_code == 400


def test_unknown_route_uses_error_shape(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert set(response.json()) == {"error"}


def test_wrong_method_uses_error_shape(client):
    response = client.put("/expenses", json=VALID)

    assert response.status_code == 405
    assert set(response.json()) == {"error"}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
