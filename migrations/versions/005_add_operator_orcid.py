"""add operator_orcid to agents

Revision ID: 005
Revises: 004
Create Date: 2026-07-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("operator_orcid", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "operator_orcid")
