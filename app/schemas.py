"""Request validation and response shapes.

Validators run in `before` mode and raise PydanticCustomError so each rule
produces exactly the message the API returns as {"error": "..."}.
"""

import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from app.errors import ApiError
from app.models import CATEGORIES

TITLE_MAX_LENGTH = 100
MAX_AMOUNT = Decimal("99999999.99")  # fits numeric(10, 2)
CENT = Decimal("0.01")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
ISO_MONTH = re.compile(r"(\d{4})-(0[1-9]|1[0-2])")
DIGITS = re.compile(r"\d+")
DEFAULT_LIMIT = 10
MAX_LIMIT = 100
MAX_PAGE = 1_000_000  # keeps OFFSET far below bigint range

# Exact Decimal internally, plain JSON number on the wire.
Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


def invalid(message: str) -> PydanticCustomError:
    return PydanticCustomError("invalid", message)


def parse_category(value: Any) -> str:
    if value not in CATEGORIES:
        raise invalid(f"category must be one of: {', '.join(CATEGORIES)}")
    return value


def parse_iso_date(value: Any, field: str) -> dt.date:
    if not isinstance(value, str) or not ISO_DATE.fullmatch(value):
        raise invalid(f"{field} must be in YYYY-MM-DD format")
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise invalid(f"{field} must be a valid calendar date") from None


# --- Requests -----------------------------------------------------------------


class ExpenseCreate(BaseModel):
    """POST /expenses body. Pass context={"today": date} when validating."""

    # Defaults of None + validate_default make "missing" go through our validators.
    title: str = Field(default=None, validate_default=True)
    amount: Decimal = Field(default=None, validate_default=True)
    category: str = Field(default=None, validate_default=True)
    date: dt.date = Field(default=None, validate_default=True)

    @field_validator("title", mode="before")
    @classmethod
    def check_title(cls, value: Any) -> str:
        if value is None or (isinstance(value, str) and not value.strip()):
            raise invalid("title is required")
        if not isinstance(value, str):
            raise invalid("title must be a string")
        value = value.strip()
        if len(value) > TITLE_MAX_LENGTH:
            raise invalid(f"title must be at most {TITLE_MAX_LENGTH} characters")
        return value

    @field_validator("amount", mode="before")
    @classmethod
    def check_amount(cls, value: Any) -> Decimal:
        if value is None:
            raise invalid("amount is required")
        # bool is a subclass of int, so reject it explicitly.
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise invalid("amount must be a number")
        try:
            # str() first so a float like 12.1 becomes Decimal("12.1"), not its binary expansion.
            amount = Decimal(str(value).strip())
        except InvalidOperation:
            raise invalid("amount must be a number") from None
        if not amount.is_finite():
            raise invalid("amount must be a number")
        if amount <= 0:
            raise invalid("amount must be greater than 0")
        if amount != amount.quantize(CENT):
            raise invalid("amount must have at most 2 decimal places")
        if amount > MAX_AMOUNT:
            raise invalid(f"amount must be at most {MAX_AMOUNT}")
        return amount.quantize(CENT)

    @field_validator("category", mode="before")
    @classmethod
    def check_category(cls, value: Any) -> str:
        if value is None:
            raise invalid("category is required")
        return parse_category(value)

    @field_validator("date", mode="before")
    @classmethod
    def check_date(cls, value: Any, info: ValidationInfo) -> dt.date:
        today: dt.date = (info.context or {}).get("today") or dt.date.today()
        if value is None or value == "":
            return today
        expense_date = parse_iso_date(value, "date")
        if expense_date > today:
            raise invalid("date cannot be in the future")
        return expense_date


def parse_bounded_int(value: Any, field: str, maximum: int) -> int:
    message = f"{field} must be an integer between 1 and {maximum}"
    if not isinstance(value, str) or not DIGITS.fullmatch(value):
        raise invalid(message)
    number = int(value)
    if not 1 <= number <= maximum:
        raise invalid(message)
    return number


class ExpenseFilters(BaseModel):
    """GET /expenses query string. Empty values are treated as "not provided"."""

    category: str | None = None
    date_from: dt.date | None = Field(default=None, alias="from")
    date_to: dt.date | None = Field(default=None, alias="to")
    page: int = 1
    limit: int = DEFAULT_LIMIT

    @model_validator(mode="before")
    @classmethod
    def drop_empty_values(cls, data: Any) -> Any:
        return {key: value for key, value in data.items() if value != ""}

    @field_validator("category", mode="before")
    @classmethod
    def check_category(cls, value: Any) -> str:
        return parse_category(value)

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def check_dates(cls, value: Any, info: ValidationInfo) -> dt.date:
        return parse_iso_date(value, "from" if info.field_name == "date_from" else "to")

    @field_validator("page", mode="before")
    @classmethod
    def check_page(cls, value: Any) -> int:
        return parse_bounded_int(value, "page", MAX_PAGE)

    @field_validator("limit", mode="before")
    @classmethod
    def check_limit(cls, value: Any) -> int:
        return parse_bounded_int(value, "limit", MAX_LIMIT)

    @model_validator(mode="after")
    def check_range(self) -> "ExpenseFilters":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise invalid("from must be on or before to")
        return self


def parse_month(value: str | None) -> tuple[dt.date, dt.date]:
    """'2026-10' -> (2026-10-01, 2026-11-01): a half-open [start, end) range."""
    if not value:
        raise ApiError(400, "month is required (YYYY-MM)")
    match = ISO_MONTH.fullmatch(value)
    if not match:
        raise ApiError(400, "month must be in YYYY-MM format")
    year, month = int(match[1]), int(match[2])
    start = dt.date(year, month, 1)
    end = dt.date(year + 1, 1, 1) if month == 12 else dt.date(year, month + 1, 1)
    return start, end


# --- Responses ----------------------------------------------------------------


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    amount: Money
    category: str
    date: dt.date = Field(validation_alias="expense_date")
    created_at: dt.datetime


class ExpenseList(BaseModel):
    items: list[ExpenseOut]
    total_count: int
    total_amount: Money  # across every row matching the filters, not just this page


class MonthlySummary(BaseModel):
    month: str
    totals: dict[str, Money]  # every category, 0 when it has no expenses
    total: Money
