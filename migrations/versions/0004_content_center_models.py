"""add raw_items and content_items tables

Revision ID: 0004_content_center_models
Revises: 0002_retry_policy
Create Date: 2026-04-24
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_content_center_models"
down_revision = "0002_retry_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "raw_items" not in table_names:
        op.create_table(
            "raw_items",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("source_id", sa.Uuid(), nullable=False),
            sa.Column("job_id", sa.Uuid(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["collection_jobs.id"]),
            sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "content_items" not in table_names:
        op.create_table(
            "content_items",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("dedupe_key", sa.String(length=128), nullable=False),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("canonical_url", sa.Text(), nullable=False),
            sa.Column("excerpt", sa.Text(), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=False),
            sa.Column("raw_payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("dedupe_key"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "content_items" in table_names:
        op.drop_table("content_items")
    if "raw_items" in table_names:
        op.drop_table("raw_items")
