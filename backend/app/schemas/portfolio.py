"""Pydantic v2 schemas for paper-trading portfolio, trades, and P&L."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PortfolioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # type: ignore[typeddict-unknown-key]
    id: uuid.UUID
    name: str
    cash_balance: Decimal
    currency: str
    created_at: datetime


class TradeCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=30)
    side: Literal["buy", "sell"]
    quantity: Decimal = Field(gt=0)
    # If price is None → market order (fill at current quote).
    price: Decimal | None = None
    notes: str | None = None


class TradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # type: ignore[typeddict-unknown-key]
    id: uuid.UUID
    portfolio_id: uuid.UUID
    symbol: str
    exchange: str
    side: str
    quantity: Decimal
    price: Decimal
    cash_delta: Decimal
    status: str
    notes: str | None
    executed_at: datetime


class Holding(BaseModel):
    symbol: str
    quantity: Decimal
    avg_cost: Decimal
    current_price: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_pct: Decimal | None
    market_value: Decimal | None


class PortfolioSummary(BaseModel):
    portfolio: PortfolioRead
    holdings: list[Holding]
    total_invested: Decimal
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    realized_pnl: Decimal
    total_pnl: Decimal | None


class OrderBookDepth(BaseModel):
    symbol: str
    bids: list[tuple[float, float]]
    asks: list[tuple[float, float]]
    best_bid: float | None
    best_ask: float | None
