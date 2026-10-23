"""Shared fixtures.

Database tests run against an isolated `test` schema in the Supabase project:
every test connection sets search_path=test, so the production table
public.expenses is never read, written or truncated.
"""

import datetime as dt
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session
from app.main import app
from app.routes import get_today

TEST_SCHEMA = "test"
TODAY = dt.date(2026, 10, 15)
MIGRATION = Path(__file__).resolve().parent.parent / "migrations" / "001_create_expenses.sql"


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    from app.config import get_settings

    try:
        url = get_settings().database_url
    except Exception:
        pytest.skip("DATABASE_URL is not set; skipping database tests")

    engine = create_engine(url, pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def use_test_schema(dbapi_connection, _record) -> None:
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f"SET search_path TO {TEST_SCHEMA}")
        dbapi_connection.commit()

    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {TEST_SCHEMA}"))
        # Raw cursor: the migration file holds several statements.
        conn.connection.cursor().execute(MIGRATION.read_text())
        assert conn.execute(text("SELECT current_schema()")).scalar() == TEST_SCHEMA

    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[sessionmaker[Session]]:
    """Empty test.expenses before each database test."""
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TEST_SCHEMA}.expenses RESTART IDENTITY"))
    yield sessionmaker(bind=engine, expire_on_commit=False)


def _client(session_override) -> Iterator[TestClient]:
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Client for requests rejected before any database access (validation)."""

    def no_database() -> Iterator[None]:
        yield None

    yield from _client(no_database)


@pytest.fixture
def db_client(db: sessionmaker[Session]) -> Iterator[TestClient]:
    """Client backed by the real test schema."""

    def test_session() -> Iterator[Session]:
        session = db()
        try:
            yield session
        finally:
            session.close()

    yield from _client(test_session)
