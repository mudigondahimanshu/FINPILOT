"""Savings-goal schemas, including projection fields computed by the service."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    icon: str = Field(default="Target", max_length=50)
    target_amount: Decimal = Field(gt=0)
    saved_amount: Decimal = Field(default=Decimal(0), ge=0)
    target_date: date | None = None


class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    icon: str | None = Field(default=None, max_length=50)
    target_amount: Decimal | None = Field(default=None, gt=0)
    target_date: date | None = None


class GoalContribute(BaseModel):
    # Negative amounts allow correcting a mistaken contribution.
    amount: Decimal


class GoalRead(BaseModel):
    id: uuid.UUID
    name: str
    icon: str
    target_amount: Decimal
    saved_amount: Decimal
    target_date: date | None
    progress_pct: float
    # Projection from the user's average monthly net savings; None when
    # there is no savings history to project from.
    projected_completion: date | None = None
    monthly_needed: Decimal | None = None  # to hit target_date, if set

    model_config = {"from_attributes": True}
