"""All database access. SQLAlchemy builds parameterized SQL, so input is never
interpolated into query text."""

import datetime as dt
from decimal import Decimal

from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.orm import Session

from app.models import CATEGORIES, Expense
from app.schemas import ExpenseCreate, ExpenseFilters

NEWEST_FIRST = (Expense.expense_date.desc(), Expense.created_at.desc(), Expense.id.desc())


def create_expense(session: Session, data: ExpenseCreate) -> Expense:
    expense = Expense(
        title=data.title, amount=data.amount, category=data.category, expense_date=data.date
    )
    session.add(expense)
    session.commit()
    return expense


def _conditions(filters: ExpenseFilters) -> list[ColumnElement[bool]]:
    conditions = []
    if filters.category:
        conditions.append(Expense.category == filters.category)
    if filters.date_from:
        conditions.append(Expense.expense_date >= filters.date_from)
    if filters.date_to:
        conditions.append(Expense.expense_date <= filters.date_to)
    return conditions


def list_expenses(
    session: Session, filters: ExpenseFilters
) -> tuple[list[Expense], int, Decimal]:
    """One page of matching expenses, plus count and sum over *all* matches."""
    conditions = _conditions(filters)

    total_count, total_amount = session.execute(
        select(func.count(), func.coalesce(func.sum(Expense.amount), 0)).where(*conditions)
    ).one()

    items = session.scalars(
        select(Expense)
        .where(*conditions)
        .order_by(*NEWEST_FIRST)
        .limit(filters.limit)
        .offset((filters.page - 1) * filters.limit)
    ).all()

    return list(items), total_count, total_amount


def delete_expense(session: Session, expense_id: int) -> bool:
    """Delete in one statement; True if a row was removed."""
    result = session.execute(delete(Expense).where(Expense.id == expense_id))
    session.commit()
    return result.rowcount == 1


def category_totals(session: Session, start: dt.date, end: dt.date) -> dict[str, Decimal]:
    """Sum per category for start <= date < end, with every category present."""
    rows = session.execute(
        select(Expense.category, func.sum(Expense.amount))
        .where(Expense.expense_date >= start, Expense.expense_date < end)
        .group_by(Expense.category)
    ).all()
    totals = dict.fromkeys(CATEGORIES, Decimal("0"))
    totals.update(rows)
    return totals
