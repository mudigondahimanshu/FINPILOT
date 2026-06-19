"""OHLC candlestick model — TimescaleDB hypertable partitioned by timestamp."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OHLC(Base):
    """One OHLC candle for a given symbol + interval."""

    __tablename__ = "ohlc"

    # Composite PK: (id, timestamp) — TimescaleDB requires the partition
    # column in the primary key.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )

    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # "1d" | "1h" | "5m" | "1m"
    interval: Mapped[str] = mapped_column(String(5), nullable=False)

    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OHLC {self.symbol} {self.interval} {self.timestamp:%Y-%m-%d}>"
