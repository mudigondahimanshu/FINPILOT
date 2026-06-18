"""Monthly spending budget per category."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.user import User

from app.core.database import Base


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )

    # 'monthly' | 'weekly' | 'yearly'
    period: Mapped[str] = mapped_column(String(10), nullable=False, server_default="monthly")
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Email alert fires when spending reaches this fraction (0–1).
    alert_threshold: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, server_default="0.80"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="budgets")
    category: Mapped[Category] = relationship("Category", back_populates="budgets")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Budget {self.category_id} {self.amount}/{self.period}>"
