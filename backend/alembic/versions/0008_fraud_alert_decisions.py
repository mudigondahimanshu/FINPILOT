"""Persist user decisions on Fraud Guard alerts.

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fraud_alert_decisions",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("decision", sa.String(10), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("decision IN ('keep', 'remove')", name="ck_fraud_alert_decision"),
    )
    op.execute("ALTER TABLE fraud_alert_decisions ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY fraud_alert_decisions_user_isolation ON fraud_alert_decisions
        USING (user_id::text = current_setting('app.user_id', true))
        WITH CHECK (user_id::text = current_setting('app.user_id', true))
        """
    )


def downgrade() -> None:
    op.drop_table("fraud_alert_decisions")
