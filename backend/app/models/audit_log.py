"""Immutable audit log — records every write operation on sensitive tables."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    """Append-only row written by trigger or application code on each mutation."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Who triggered the action (nullable — system operations have no user).
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    # Which table + row was touched.
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    row_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # 'INSERT' | 'UPDATE' | 'DELETE'
    action: Mapped[str] = mapped_column(String(10), nullable=False)

    # JSON snapshot (nullable for INSERT/DELETE where one side is trivial).
    old_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.action} {self.table_name}/{self.row_id}>"
