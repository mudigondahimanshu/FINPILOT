"""users table + row-level security

Revision ID: 0001_users
Revises:
Create Date: 2026-06-17

RLS design (default-deny):
  * `app.user_id`  — set per authenticated request; a row is visible only when
                     its id matches. Users can touch only their own row.
  * `app.auth_ctx` — set to 'on' by the auth service for pre-auth lookups
                     (login-by-email, registration insert). Controlled bypass.
  FORCE ROW LEVEL SECURITY makes policies apply even to the table owner role.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_users"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column(
            "auth_provider",
            sa.String(length=20),
            server_default="local",
            nullable=False,
        ),
        sa.Column("google_sub", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column(
            "is_verified", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)

    # --- Row-Level Security ---
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")

    # Self-access: a request that set app.user_id can only see/modify that row.
    op.execute(
        """
        CREATE POLICY users_self ON users
        USING (id = current_setting('app.user_id', true)::uuid)
        WITH CHECK (id = current_setting('app.user_id', true)::uuid)
        """
    )

    # Auth context: controlled bypass for login-by-email and registration.
    op.execute(
        """
        CREATE POLICY users_auth_ctx ON users
        USING (current_setting('app.auth_ctx', true) = 'on')
        WITH CHECK (current_setting('app.auth_ctx', true) = 'on')
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS users_auth_ctx ON users")
    op.execute("DROP POLICY IF EXISTS users_self ON users")
    op.execute("ALTER TABLE users NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
