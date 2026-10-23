"""ORM mapping for the expenses table (schema lives in migrations/001_create_expenses.sql)."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Identity, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

CATEGORIES = ("food", "travel", "bills", "other")


class Base(DeclarativeBase):
    pass


class Expense(Base):
    __tablename__ = "expenses"
    # Fetch server-generated columns (id, created_at) with INSERT ... RETURNING.
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    category: Mapped[str] = mapped_column(Text)
    expense_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
