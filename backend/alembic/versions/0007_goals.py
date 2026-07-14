"""Phase 5 — savings goals.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("icon", sa.String(50), nullable=False, server_default="Target"),
        sa.Column("target_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("saved_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.execute("ALTER TABLE goals ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY goals_user_isolation ON goals
        USING (user_id::text = current_setting('app.user_id', true))
        """
    )


def downgrade() -> None:
    op.drop_table("goals")
