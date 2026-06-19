"""Phase 3b — classifier feedback, user preferences, A/B assignments, confidence columns.

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"  # 0004_ml
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 3.1 Confidence + override tracking on transactions ────────────────────
    op.add_column("transactions", sa.Column("ml_confidence", sa.Float(), nullable=True))
    op.add_column("transactions", sa.Column("ml_category_override", sa.Boolean(), nullable=True, server_default="false"))

    # ── 3.1 Classifier feedback (manual overrides → future retraining) ────────
    op.create_table(
        "classifier_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),  # no FK: transactions is a hypertable with composite PK
        sa.Column("original_category", sa.String(64), nullable=True),
        sa.Column("corrected_category", sa.String(64), nullable=False),
        sa.Column("description", sa.String(512), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute("ALTER TABLE classifier_feedback ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY classifier_feedback_user_isolation ON classifier_feedback
        USING (user_id::text = current_setting('app.user_id', true))
    """)

    # ── 3.6 Per-user preference embedding ─────────────────────────────────────
    op.create_table(
        "user_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("embedding", sa.Text(), nullable=True),           # JSON-serialised vector(384)
        sa.Column("top_categories", postgresql.JSONB(), nullable=True),  # {category: spend_pct}
        sa.Column("risk_profile", sa.String(16), nullable=True),    # conservative|moderate|aggressive
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute("ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY user_preferences_isolation ON user_preferences
        USING (user_id::text = current_setting('app.user_id', true))
    """)

    # ── 3.6 A/B experiment assignments ────────────────────────────────────────
    op.create_table(
        "ab_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("experiment", sa.String(64), nullable=False),     # e.g. "bandit_v2"
        sa.Column("variant", sa.String(16), nullable=False),        # "control" | "treatment"
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_ab_assignments_user_experiment", "ab_assignments", ["user_id", "experiment"])
    op.execute("ALTER TABLE ab_assignments ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY ab_assignments_isolation ON ab_assignments
        USING (user_id::text = current_setting('app.user_id', true))
    """)

    # ── 3.5 Copilot chat feedback ──────────────────────────────────────────────
    op.create_table(
        "copilot_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("thumbs_up", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute("ALTER TABLE copilot_feedback ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY copilot_feedback_isolation ON copilot_feedback
        USING (user_id::text = current_setting('app.user_id', true))
    """)


def downgrade() -> None:
    op.drop_table("copilot_feedback")
    op.drop_table("ab_assignments")
    op.drop_table("user_preferences")
    op.drop_table("classifier_feedback")
    op.drop_column("transactions", "ml_category_override")
    op.drop_column("transactions", "ml_confidence")
