"""Budget CRUD schemas. Progress/status lives in schemas.transaction.BudgetStatus."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class BudgetCreate(BaseModel):
    category_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    period: str = Field(default="monthly", pattern="^(weekly|monthly|yearly)$")
    alert_threshold: Decimal = Field(default=Decimal("0.80"), ge=0, le=1)


class BudgetUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0)
    period: str | None = Field(default=None, pattern="^(weekly|monthly|yearly)$")
    alert_threshold: Decimal | None = Field(default=None, ge=0, le=1)


class BudgetRead(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    amount: Decimal
    period: str
    alert_threshold: Decimal

    model_config = {"from_attributes": True}
