"""add ssh keys

Revision ID: 004
Revises: 003
Create Date: 2026-06-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ssh_keys",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("key_fingerprint", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ssh_keys_user_id", "ssh_keys", ["user_id"])
    op.create_index("ix_ssh_keys_key_fingerprint", "ssh_keys", ["key_fingerprint"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ssh_keys_key_fingerprint", table_name="ssh_keys")
    op.drop_index("ix_ssh_keys_user_id", table_name="ssh_keys")
    op.drop_table("ssh_keys")
