"""Phase 2 — OHLC hypertable + watchlist table.

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ohlc ─────────────────────────────────────────────────────────────────
    op.create_table(
        "ohlc",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("interval", sa.String(5), nullable=False),
        sa.Column("open", sa.Numeric(18, 4), nullable=False),
        sa.Column("high", sa.Numeric(18, 4), nullable=False),
        sa.Column("low", sa.Numeric(18, 4), nullable=False),
        sa.Column("close", sa.Numeric(18, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", "timestamp"),
    )
    op.create_index("ix_ohlc_symbol_interval_ts", "ohlc", ["symbol", "interval", "timestamp"])

    # Promote to TimescaleDB hypertable partitioned by timestamp (1-day chunks).
    op.execute(
        "SELECT create_hypertable('ohlc', 'timestamp',"
        " chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)"
    )

    # Unique constraint so we don't double-insert the same candle.
    op.execute(
        "CREATE UNIQUE INDEX uq_ohlc_symbol_interval_ts "
        "ON ohlc (symbol, interval, timestamp)"
    )

    # ── watchlist ─────────────────────────────────────────────────────────────
    op.create_table(
        "watchlist",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("exchange", sa.String(10), server_default="NSE", nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),
    )
    op.create_index("ix_watchlist_user_id", "watchlist", ["user_id"])

    # RLS on watchlist
    op.execute("ALTER TABLE watchlist ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE watchlist FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY watchlist_self ON watchlist
        USING (user_id = current_setting('app.user_id', true)::uuid)
        WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY watchlist_auth_ctx ON watchlist
        USING (current_setting('app.auth_ctx', true) = 'on')
        WITH CHECK (current_setting('app.auth_ctx', true) = 'on')
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS watchlist CASCADE")
    op.execute("DROP TABLE IF EXISTS ohlc CASCADE")
