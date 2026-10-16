"""add self-registration and claim columns to agents

Revision ID: 010
Revises: 009
Create Date: 2026-10-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("registration_source", sa.String(20), nullable=False, server_default="operator"),
    )
    op.add_column("agents", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agents", sa.Column("agent_secret_hash", sa.String(64), nullable=True))
    op.add_column("agents", sa.Column("operator_email_hint", sa.String(255), nullable=True))
    op.add_column("agents", sa.Column("operator_telegram", sa.String(255), nullable=True))
    op.add_column("agents", sa.Column("operator_x", sa.String(255), nullable=True))


def downgrade() -> None:
    for column in (
        "operator_x",
        "operator_telegram",
        "operator_email_hint",
        "agent_secret_hash",
        "claimed_at",
        "registration_source",
    ):
        op.drop_column("agents", column)
