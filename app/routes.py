"""HTTP layer for /expenses: parse input, call the repository, choose status codes."""

import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Request, Response
from sqlalchemy.orm import Session

from app import repository
from app.config import get_settings
from app.db import get_session
from app.errors import ApiError
from app.schemas import (
    DIGITS,
    ExpenseCreate,
    ExpenseFilters,
    ExpenseList,
    ExpenseOut,
    MonthlySummary,
    parse_month,
)

router = APIRouter(prefix="/expenses", tags=["expenses"])

MAX_ID = 2**63 - 1  # bigint


def get_today() -> dt.date:
    """Today's date in the configured timezone. A dependency so tests can pin it."""
    return dt.datetime.now(get_settings().timezone).date()


SessionDep = Annotated[Session, Depends(get_session)]
TodayDep = Annotated[dt.date, Depends(get_today)]


@router.post("", status_code=201, response_model=ExpenseOut)
def create_expense(
    session: SessionDep, today: TodayDep, payload: Annotated[Any, Body()] = None
) -> ExpenseOut:
    # The body is validated explicitly (not as a typed parameter) so the
    # "no future dates" rule can use the injected `today`.
    if not isinstance(payload, dict):
        raise ApiError(400, "Request body must be a JSON object")
    data = ExpenseCreate.model_validate(payload, context={"today": today})
    return ExpenseOut.model_validate(repository.create_expense(session, data))


@router.get("", response_model=ExpenseList)
def list_expenses(request: Request, session: SessionDep) -> ExpenseList:
    filters = ExpenseFilters.model_validate(dict(request.query_params))
    items, total_count, total_amount = repository.list_expenses(session, filters)
    return ExpenseList(
        items=[ExpenseOut.model_validate(item) for item in items],
        total_count=total_count,
        total_amount=total_amount,
    )


# Declared before /{expense_id} for readability; methods differ, so they never clash.
@router.get("/summary", response_model=MonthlySummary)
def monthly_summary(session: SessionDep, month: str | None = None) -> MonthlySummary:
    start, end = parse_month(month)
    totals = repository.category_totals(session, start, end)
    return MonthlySummary(month=month, totals=totals, total=sum(totals.values()))


@router.delete("/{expense_id}", status_code=204)
def delete_expense(expense_id: str, session: SessionDep) -> Response:
    # An id that isn't a valid bigint can't exist, so it's "not found", not "bad input".
    if not DIGITS.fullmatch(expense_id) or not 1 <= int(expense_id) <= MAX_ID:
        raise ApiError(404, "Expense not found")
    if not repository.delete_expense(session, int(expense_id)):
        raise ApiError(404, "Expense not found")
    return Response(status_code=204)
