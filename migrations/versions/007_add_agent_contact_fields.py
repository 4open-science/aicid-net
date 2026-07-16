"""add agent contact fields

Revision ID: 007
Revises: 006
Create Date: 2026-07-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("agent_email", sa.String(255), nullable=True))
    op.add_column("agents", sa.Column("agent_telegram", sa.String(255), nullable=True))
    op.add_column("agents", sa.Column("agent_discord", sa.String(255), nullable=True))
    op.add_column("agents", sa.Column("agent_twitter", sa.String(255), nullable=True))
    op.add_column("agents", sa.Column("agent_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "agent_url")
    op.drop_column("agents", "agent_twitter")
    op.drop_column("agents", "agent_discord")
    op.drop_column("agents", "agent_telegram")
    op.drop_column("agents", "agent_email")
