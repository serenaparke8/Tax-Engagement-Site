"""Create the TEMS PostgreSQL schema.

Revision ID: 20261121_01
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261121_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index(
        "uq_users_username_lower",
        "users",
        [sa.text("lower(username)")],
        unique=True,
    )
    op.create_table(
        "client",
        sa.Column("client_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_name", sa.Text(), nullable=False),
        sa.Column("contact_name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("client_id"),
    )
    op.create_table(
        "tax_engagement",
        sa.Column("engagement_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("return_type", sa.Text(), nullable=False),
        sa.Column("assigned_preparer", sa.Text(), nullable=False),
        sa.Column("engagement_start_date", sa.Text(), nullable=False),
        sa.Column("filing_deadline", sa.Text(), nullable=False),
        sa.Column("engagement_status", sa.Text(), server_default="In Progress", nullable=False),
        sa.CheckConstraint(
            "engagement_status IN ('In Progress', 'Waiting on Client', 'Completed')",
            name="ck_tax_engagement_status",
        ),
        sa.ForeignKeyConstraint(["client_id"], ["client.client_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("engagement_id"),
    )
    op.create_index("idx_tax_engagement_client_id", "tax_engagement", ["client_id"])
    op.create_table(
        "required_item",
        sa.Column("required_item_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("engagement_id", sa.Integer(), nullable=False),
        sa.Column("required_item_description", sa.Text(), nullable=False),
        sa.Column("item_status", sa.Text(), server_default="Outstanding", nullable=False),
        sa.CheckConstraint(
            "item_status IN ('Outstanding', 'Received')",
            name="ck_required_item_status",
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id"], ["tax_engagement.engagement_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("required_item_id"),
    )
    op.create_index("idx_required_item_engagement_id", "required_item", ["engagement_id"])


def downgrade() -> None:
    op.drop_index("idx_required_item_engagement_id", table_name="required_item")
    op.drop_table("required_item")
    op.drop_index("idx_tax_engagement_client_id", table_name="tax_engagement")
    op.drop_table("tax_engagement")
    op.drop_table("client")
    op.drop_index("uq_users_username_lower", table_name="users")
    op.drop_table("users")
