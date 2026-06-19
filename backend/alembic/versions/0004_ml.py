"""Phase 3 ML schema: recommendation_feedback + embeddings vector(384).

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Change embeddings vector dimension from 1536 → 384 (sentence-transformers).
    # Safe because the table is empty in dev (no real user data yet).
    op.execute("ALTER TABLE embeddings DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE embeddings ADD COLUMN embedding vector(384)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS embeddings_vector_idx "
        "ON embeddings USING hnsw (embedding vector_cosine_ops)"
    )

    # Recommendation feedback table (3.6 bandit logging)
    op.create_table(
        "recommendation_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.UUID, nullable=False, index=True),
        sa.Column("arm", sa.String(64), nullable=False),
        sa.Column("context", sa.JSON, nullable=True),
        sa.Column("accepted", sa.Boolean, nullable=True),
        sa.Column("shown_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_rec_fb_arm", "recommendation_feedback", ["arm"])

    # RLS on recommendation_feedback
    op.execute("ALTER TABLE recommendation_feedback ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE recommendation_feedback FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY rec_fb_self ON recommendation_feedback
        USING (user_id::text = current_setting('app.user_id', TRUE))
        """
    )
    op.execute(
        """
        CREATE POLICY rec_fb_auth_ctx ON recommendation_feedback
        USING (current_setting('app.auth_ctx', TRUE) = 'on')
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recommendation_feedback")
    op.execute("DROP INDEX IF EXISTS embeddings_vector_idx")
    op.execute("ALTER TABLE embeddings DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE embeddings ADD COLUMN embedding vector(1536)")
