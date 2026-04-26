"""add subscriptions and delivery_records tables

Revision ID: 0005_subscriptions_and_delivery_records
Revises: 0004_content_center_models
Create Date: 2026-04-24
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_subscriptions_and_delivery_records"
down_revision = "0004_content_center_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "subscriptions" not in table_names:
        op.create_table(
            "subscriptions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("code", sa.String(length=100), nullable=False),
            sa.Column("channel", sa.String(length=30), nullable=False),
            sa.Column("business_lines", sa.JSON(), nullable=False),
            sa.Column("keywords", sa.JSON(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )

    if "delivery_records" not in table_names:
        op.create_table(
            "delivery_records",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("subscription_id", sa.Uuid(), nullable=False),
            sa.Column("content_item_id", sa.Uuid(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"]),
            sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("subscription_id", "content_item_id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "delivery_records" in table_names:
        op.drop_table("delivery_records")
    if "subscriptions" in table_names:
        op.drop_table("subscriptions")
