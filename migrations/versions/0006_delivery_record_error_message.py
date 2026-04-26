"""add delivery_records.error_message

Revision ID: 0006_delivery_record_error_message
Revises: 0005_subscriptions_and_delivery_records
Create Date: 2026-04-24
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_delivery_record_error_message"
down_revision = "0005_subscriptions_and_delivery_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "delivery_records" not in table_names:
        return

    columns = {column["name"] for column in inspector.get_columns("delivery_records")}
    if "error_message" not in columns:
        with op.batch_alter_table("delivery_records") as batch_op:
            batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "delivery_records" not in table_names:
        return

    columns = {column["name"] for column in inspector.get_columns("delivery_records")}
    if "error_message" in columns:
        with op.batch_alter_table("delivery_records") as batch_op:
            batch_op.drop_column("error_message")
