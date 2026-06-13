"""add auth challenges

Revision ID: 003
Revises: 002
Create Date: 2026-06-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_challenges",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("purpose", sa.String(50), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_auth_challenges_email", "auth_challenges", ["email"])
    op.create_index("ix_auth_challenges_token_hash", "auth_challenges", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_auth_challenges_token_hash", table_name="auth_challenges")
    op.drop_index("ix_auth_challenges_email", table_name="auth_challenges")
    op.drop_table("auth_challenges")
