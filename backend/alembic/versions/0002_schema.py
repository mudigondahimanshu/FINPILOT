"""Full domain schema: accounts, categories, transactions (hypertable), budgets,
portfolios, trades, audit_logs, embeddings (pgvector).

Revision ID: 0002_schema
Revises: 0001_users
Create Date: 2026-06-18

TimescaleDB:
  transactions.date is the partitioning column.  The hypertable is created
  immediately after the plain table so that existing SQLAlchemy tooling (which
  only sees a regular Postgres table) keeps working.

pgvector:
  The `vector` extension is enabled in the DB init script.  We add a dedicated
  `embedding_vectors` column (type `vector(1536)`) and an HNSW ANN index here;
  the ORM model uses a JSONB shadow column so the Python side doesn't need the
  pgvector package at import time.

RLS:
  All user-owned tables follow the same two-policy pattern as `users`:
    * <table>_self  — active when app.user_id is set (normal requests)
    * <table>_auth_ctx — controlled bypass (same app.auth_ctx GUC used by auth)
  Categories are special: system rows (user_id IS NULL) are globally readable.
  audit_logs are write-only to the app role (read by owner's user_id).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_schema"
down_revision: Union[str, None] = "0001_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def _self_policy(table: str) -> None:
    """Standard per-user read/write policy based on app.user_id GUC."""
    op.execute(
        f"""
        CREATE POLICY {table}_self ON {table}
        USING (user_id = current_setting('app.user_id', true)::uuid)
        WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
        """
    )


def _auth_ctx_policy(table: str) -> None:
    """Controlled bypass for service-layer code (auth service, etc.)."""
    op.execute(
        f"""
        CREATE POLICY {table}_auth_ctx ON {table}
        USING (current_setting('app.auth_ctx', true) = 'on')
        WITH CHECK (current_setting('app.auth_ctx', true) = 'on')
        """
    )


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:

    # ── accounts ─────────────────────────────────────────────────────────────
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("institution", sa.String(255), nullable=True),
        sa.Column("account_type", sa.String(30), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("external_ref", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_accounts_user_id", "accounts", ["user_id"])
    _enable_rls("accounts")
    _self_policy("accounts")
    _auth_ctx_policy("accounts")

    # ── categories ───────────────────────────────────────────────────────────
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("icon", sa.String(50), server_default="Tag", nullable=False),
        sa.Column("color", sa.String(7), server_default="#6B7280", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_categories_user_id", "categories", ["user_id"])
    _enable_rls("categories")
    # User can see their own categories OR system-wide ones.
    op.execute(
        """
        CREATE POLICY categories_self ON categories
        USING (
            user_id = current_setting('app.user_id', true)::uuid
            OR user_id IS NULL
        )
        WITH CHECK (
            user_id = current_setting('app.user_id', true)::uuid
        )
        """
    )
    _auth_ctx_policy("categories")

    # Seed system categories.
    op.execute(
        """
        INSERT INTO categories (id, user_id, name, icon, color, is_system)
        VALUES
          (gen_random_uuid(), NULL, 'Food & Dining',      'UtensilsCrossed', '#F59E0B', true),
          (gen_random_uuid(), NULL, 'Transport',          'Car',             '#3B82F6', true),
          (gen_random_uuid(), NULL, 'Shopping',           'ShoppingCart',    '#EC4899', true),
          (gen_random_uuid(), NULL, 'Entertainment',      'Film',            '#8B5CF6', true),
          (gen_random_uuid(), NULL, 'Health & Medical',   'Heart',           '#EF4444', true),
          (gen_random_uuid(), NULL, 'Utilities & Bills',  'Zap',             '#10B981', true),
          (gen_random_uuid(), NULL, 'Travel',             'Plane',           '#06B6D4', true),
          (gen_random_uuid(), NULL, 'Education',          'BookOpen',        '#6366F1', true),
          (gen_random_uuid(), NULL, 'Salary & Income',   'TrendingUp',      '#22C55E', true),
          (gen_random_uuid(), NULL, 'Investments',        'LineChart',       '#A78BFA', true),
          (gen_random_uuid(), NULL, 'Other',              'Tag',             '#6B7280', true)
        """
    )

    # ── transactions (TimescaleDB hypertable) ─────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("description", sa.String(512), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("source", sa.String(30), server_default="manual", nullable=False),
        sa.Column("merchant", sa.String(255), nullable=True),
        sa.Column("is_recurring", sa.Boolean, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", "date"),  # composite PK required for hypertable
    )
    # Promote to TimescaleDB hypertable partitioned by date (7-day chunks).
    op.execute(
        "SELECT create_hypertable('transactions', 'date', chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
    )
    # Core query patterns: per-user time range + per-user category filter.
    op.create_index("ix_txn_user_date",     "transactions", ["user_id", "date"])
    op.create_index("ix_txn_user_category", "transactions", ["user_id", "category_id"])
    op.create_index("ix_txn_account",       "transactions", ["account_id"])

    _enable_rls("transactions")
    _self_policy("transactions")
    _auth_ctx_policy("transactions")

    # ── budgets ───────────────────────────────────────────────────────────────
    op.create_table(
        "budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period", sa.String(10), server_default="monthly", nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("alert_threshold", sa.Numeric(4, 2), server_default="0.80", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_budgets_user_id", "budgets", ["user_id"])
    _enable_rls("budgets")
    _self_policy("budgets")
    _auth_ctx_policy("budgets")

    # ── portfolios ────────────────────────────────────────────────────────────
    op.create_table(
        "portfolios",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), server_default="My Portfolio", nullable=False),
        sa.Column("cash_balance", sa.Numeric(18, 2), server_default="100000", nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolios_user_id", "portfolios", ["user_id"])
    _enable_rls("portfolios")
    _self_policy("portfolios")
    _auth_ctx_policy("portfolios")

    # ── trades ────────────────────────────────────────────────────────────────
    op.create_table(
        "trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("exchange", sa.String(10), server_default="NSE", nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("price", sa.Numeric(18, 2), nullable=False),
        sa.Column("cash_delta", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(12), server_default="filled", nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trades_portfolio_id", "trades", ["portfolio_id"])
    op.create_index("ix_trades_user_id",      "trades", ["user_id"])
    op.create_index("ix_trades_symbol",       "trades", ["symbol"])
    _enable_rls("trades")
    _self_policy("trades")
    _auth_ctx_policy("trades")

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("table_name", sa.String(100), nullable=False),
        sa.Column("row_id", sa.String(100), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("old_values", postgresql.JSONB, nullable=True),
        sa.Column("new_values", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_user_id",    "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    # Audit logs: owner can read their own; writes bypass via auth_ctx.
    _enable_rls("audit_logs")
    op.execute(
        """
        CREATE POLICY audit_logs_self ON audit_logs
        FOR SELECT
        USING (user_id = current_setting('app.user_id', true)::uuid)
        """
    )
    _auth_ctx_policy("audit_logs")

    # ── embeddings (pgvector) ─────────────────────────────────────────────────
    op.create_table(
        "embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("vector_json", postgresql.JSONB, nullable=True),
        sa.Column("model", sa.String(100), server_default="text-embedding-3-small", nullable=False),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Add the native vector column (pgvector) — dimension matches text-embedding-3-small.
    op.execute("ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS embedding vector(1536)")
    # HNSW index for fast approximate nearest-neighbour search (cosine distance).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_embeddings_hnsw ON embeddings USING hnsw (embedding vector_cosine_ops)"
    )
    op.create_index("ix_embeddings_user_source", "embeddings", ["user_id", "source_type"])
    _enable_rls("embeddings")
    _self_policy("embeddings")
    _auth_ctx_policy("embeddings")


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    for tbl in ["embeddings", "audit_logs", "trades", "portfolios", "budgets", "transactions", "categories", "accounts"]:
        # Drop all policies first.
        for policy in [f"{tbl}_self", f"{tbl}_auth_ctx"]:
            op.execute(f"DROP POLICY IF EXISTS {policy} ON {tbl}")
        # Audit logs has a differently named SELECT policy.
        op.execute(f"DROP POLICY IF EXISTS audit_logs_self ON {tbl}")
        op.execute(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY")
        op.drop_table(tbl)
