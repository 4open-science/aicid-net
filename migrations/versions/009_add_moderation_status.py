"""add moderation_status to agents

Revision ID: 009
Revises: 008
Create Date: 2026-10-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("moderation_status", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "moderation_status")
