"""add orcid_id and orcid_verified to users

Revision ID: 006
Revises: 005
Create Date: 2026-07-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("orcid_id", sa.String(64), nullable=True))
    op.add_column(
        "users",
        sa.Column("orcid_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "orcid_verified")
    op.drop_column("users", "orcid_id")
