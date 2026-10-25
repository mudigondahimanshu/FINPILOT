"""Per-user review choice for a transaction surfaced by Fraud Guard."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

FraudAlertChoice = Literal["keep", "remove"]


class FraudAlertDecision(Base):
    __tablename__ = "fraud_alert_decisions"
    __table_args__ = (
        CheckConstraint("decision IN ('keep', 'remove')", name="ck_fraud_alert_decision"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
