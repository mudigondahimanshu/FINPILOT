"""Phase 4 — Security hardening: MFA fields, pgcrypto, PII columns.

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgcrypto for field-level AES encryption
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # MFA columns on users
    op.add_column("users", sa.Column("totp_secret", sa.String(255), nullable=True))
    op.add_column(
        "users",
        sa.Column("mfa_enabled", sa.Boolean(), server_default="false", nullable=False),
    )

    # WebAuthn credentials table (passwordless)
    op.create_table(
        "webauthn_credentials",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("credential_id", sa.Text(), nullable=False, unique=True),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("sign_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("device_name", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.execute(
        "ALTER TABLE webauthn_credentials ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY webauthn_user_policy ON webauthn_credentials
            USING (user_id = (current_setting('app.user_id', true))::uuid)
        """
    )

    # PII audit log — stores masked / tokenised versions for compliance
    op.create_table(
        "pii_audit",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
            index=True,
        ),
        sa.Column("field_name", sa.String(64), nullable=False),
        sa.Column("token", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("pii_audit")
    op.drop_table("webauthn_credentials")
    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "totp_secret")
