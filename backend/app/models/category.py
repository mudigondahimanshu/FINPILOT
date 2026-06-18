"""Transaction categories — system defaults + user custom."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.budget import Budget
    from app.models.transaction import Transaction
    from app.models.user import User


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # NULL → system / shared category visible to all users.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # lucide-react icon name e.g. "ShoppingCart"
    icon: Mapped[str] = mapped_column(String(50), nullable=False, server_default="Tag")
    # Hex colour for charts e.g. "#6366F1"
    color: Mapped[str] = mapped_column(String(7), nullable=False, server_default="#6B7280")

    # System categories cannot be deleted or renamed by users.
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped[User | None] = relationship("User", back_populates="categories")
    transactions: Mapped[list[Transaction]] = relationship(
        "Transaction", back_populates="category"
    )
    budgets: Mapped[list[Budget]] = relationship(
        "Budget", back_populates="category", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Category {self.name}>"
