"""Financial transaction — the core time-series table.

Stored in a TimescaleDB hypertable partitioned on `date`. The (user_id, date)
composite index keeps per-user range queries fast even with millions of rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.category import Category
    from app.models.user import User

from app.core.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    # TimescaleDB partitions by this column — MUST be not-null.
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Positive = credit/income; negative = debit/expense (sign-convention).
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")

    description: Mapped[str] = mapped_column(String(512), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 'csv_import' | 'manual' | 'bank_sync'
    source: Mapped[str] = mapped_column(String(30), nullable=False, server_default="manual")

    # Merchant / counterparty extracted by NLP (Phase 2)
    merchant: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Flags
    is_recurring: Mapped[bool | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="transactions")
    account: Mapped[Account | None] = relationship("Account", back_populates="transactions")
    category: Mapped[Category | None] = relationship("Category", back_populates="transactions")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Transaction {self.date:%Y-%m-%d} {self.amount}>"
