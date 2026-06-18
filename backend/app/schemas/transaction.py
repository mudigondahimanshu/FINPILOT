"""Pydantic v2 schemas for transactions, categories, and aggregations."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

# ── Category ─────────────────────────────────────────────────────────────────

class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    icon: str
    color: str
    is_system: bool


# ── Transaction ───────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    date: datetime
    amount: Decimal = Field(description="Positive=income, negative=expense")
    currency: str = Field(default="INR", max_length=3)
    description: str = Field(min_length=1, max_length=512)
    notes: str | None = None
    category_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    source: str = Field(default="manual", max_length=30)
    merchant: str | None = None


class TransactionUpdate(BaseModel):
    date: datetime | None = None
    amount: Decimal | None = None
    description: str | None = Field(default=None, max_length=512)
    notes: str | None = None
    category_id: uuid.UUID | None = None
    merchant: str | None = None


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date: datetime
    amount: Decimal
    currency: str
    description: str
    notes: str | None
    source: str
    merchant: str | None
    is_recurring: bool | None
    category_id: uuid.UUID | None
    account_id: uuid.UUID | None
    category: CategoryRead | None
    created_at: datetime


class TransactionPage(BaseModel):
    items: list[TransactionRead]
    total: int
    page: int
    page_size: int
    has_next: bool


# ── Aggregation responses ─────────────────────────────────────────────────────

class CategorySpend(BaseModel):
    category_id: uuid.UUID | None
    category_name: str
    category_color: str
    total: Decimal
    count: int


class MonthlyTrend(BaseModel):
    month: str          # "2026-01"
    income: Decimal
    expenses: Decimal
    net: Decimal


class SpendingSummary(BaseModel):
    by_category: list[CategorySpend]
    monthly_trend: list[MonthlyTrend]
    total_income: Decimal
    total_expenses: Decimal
    savings_rate: Decimal   # (income - |expenses|) / income, 0-1


# ── CSV upload ────────────────────────────────────────────────────────────────

class CsvUploadResult(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


# ── Budget alert ──────────────────────────────────────────────────────────────

class BudgetStatus(BaseModel):
    budget_id: uuid.UUID
    category_name: str
    period: str
    budget_amount: Decimal
    spent: Decimal
    remaining: Decimal
    utilisation: Decimal    # 0-1
    alert_threshold: Decimal
    over_budget: bool
