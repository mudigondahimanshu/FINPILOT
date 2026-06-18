"""Paper-trading portfolio and trade log."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.user import User

from app.core.database import Base


class Portfolio(Base):
    """Paper-money portfolio — each user starts with a virtual cash balance."""

    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, server_default="My Portfolio")
    # Virtual cash remaining (starts at ₹1,00,000 per brief).
    cash_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, server_default="100000"
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="portfolios")
    trades: Mapped[list[Trade]] = relationship(
        "Trade", back_populates="portfolio", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Portfolio {self.name}>"


class Trade(Base):
    """Single paper trade (buy or sell) recorded in a portfolio."""

    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # NSE/BSE ticker e.g. "RELIANCE.NS"
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False, server_default="NSE")

    # 'buy' | 'sell'
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Computed at execution time: side='buy' → negative cash delta, sell → positive.
    cash_delta: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # 'filled' | 'cancelled' | 'pending'
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="filled")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    portfolio: Mapped[Portfolio] = relationship("Portfolio", back_populates="trades")
    user: Mapped[User] = relationship("User", back_populates="trades")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Trade {self.side.upper()} {self.quantity}×{self.symbol} @ {self.price}>"
