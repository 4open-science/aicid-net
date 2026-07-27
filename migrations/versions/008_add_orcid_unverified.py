"""add orcid_unverified to agents

Revision ID: 008
Revises: 007
Create Date: 2026-07-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("orcid_unverified", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "orcid_unverified")
