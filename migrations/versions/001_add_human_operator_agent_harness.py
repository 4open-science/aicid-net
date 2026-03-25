"""add human_operator and agent_harness to agents

Revision ID: 001
Revises:
Create Date: 2026-03-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("human_operator", sa.String(255), nullable=True))
    op.add_column("agents", sa.Column("agent_harness", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "agent_harness")
    op.drop_column("agents", "human_operator")
