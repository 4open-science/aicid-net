"""initial schema with all tables

Revision ID: 001
Revises:
Create Date: 2026-03-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("email", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "agents",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("aicid", sa.String(32), unique=True, index=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("human_operator", sa.String(255), nullable=True),
        sa.Column("agent_harness", sa.String(255), nullable=True),
        sa.Column("agent_type", sa.String(50), nullable=False, server_default="autonomous_agent"),
        sa.Column("base_model", sa.String(255), nullable=True),
        sa.Column("version", sa.String(100), nullable=True),
        sa.Column("organization", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("keywords", sa.Text(), nullable=True),
        sa.Column("website_url", sa.String(500), nullable=True),
        sa.Column("github_url", sa.String(500), nullable=True),
        sa.Column("paper_url", sa.String(500), nullable=True),
        sa.Column("visibility", sa.String(20), server_default="public"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "works",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("put_code", sa.String(100), index=True),
        sa.Column("work_type", sa.String(50), server_default="paper"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("doi", sa.String(255), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("journal", sa.String(255), nullable=True),
        sa.Column("published_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "employments",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("organization", sa.String(255), nullable=False),
        sa.Column("role", sa.String(255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "fundings",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("funder", sa.String(255), nullable=True),
        sa.Column("grant_number", sa.String(100), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "oauth_clients",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("client_id", sa.String(100), unique=True, index=True, nullable=False),
        sa.Column("client_secret_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("redirect_uris", sa.Text(), nullable=False),
        sa.Column("scopes", sa.String(500), server_default="read:agent"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("oauth_clients.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("access_token", sa.String(500), unique=True, index=True, nullable=False),
        sa.Column("scopes", sa.String(500), server_default="read:agent"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "oauth_auth_codes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("oauth_clients.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("scopes", sa.String(500), server_default="read:agent"),
        sa.Column("redirect_uri", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("oauth_auth_codes")
    op.drop_table("oauth_tokens")
    op.drop_table("oauth_clients")
    op.drop_table("fundings")
    op.drop_table("employments")
    op.drop_table("works")
    op.drop_table("agents")
    op.drop_table("users")
