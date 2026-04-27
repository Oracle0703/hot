"""add site_accounts and sources.account_id

Revision ID: 0007_site_accounts_and_source_account_binding
Revises: 0006_delivery_record_error_message
Create Date: 2026-04-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_site_accounts_and_source_account_binding"
down_revision = "0006_delivery_record_error_message"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "site_accounts" not in table_names:
        op.create_table(
            "site_accounts",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("platform", sa.String(length=50), nullable=False),
            sa.Column("account_key", sa.String(length=100), nullable=False),
            sa.Column("display_name", sa.String(length=100), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("platform", "account_key"),
        )

    if "sources" not in table_names:
        return

    columns = {column["name"] for column in inspector.get_columns("sources")}
    if "account_id" not in columns:
        with op.batch_alter_table("sources") as batch_op:
            batch_op.add_column(sa.Column("account_id", sa.Uuid(), nullable=True))
            batch_op.create_foreign_key("fk_sources_account_id_site_accounts", "site_accounts", ["account_id"], ["id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "sources" in table_names:
        columns = {column["name"] for column in inspector.get_columns("sources")}
        if "account_id" in columns:
            foreign_keys = {fk.get("name") for fk in inspector.get_foreign_keys("sources")}
            with op.batch_alter_table("sources") as batch_op:
                if "fk_sources_account_id_site_accounts" in foreign_keys:
                    batch_op.drop_constraint("fk_sources_account_id_site_accounts", type_="foreignkey")
                batch_op.drop_column("account_id")

    if "site_accounts" in table_names:
        op.drop_table("site_accounts")
