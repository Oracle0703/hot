"""add retry_policy column to sources

Revision ID: 0002_retry_policy
Revises: 0001_baseline
Create Date: 2026-04-23

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_retry_policy"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("sources")}
    if "retry_policy" not in cols:
        with op.batch_alter_table("sources") as batch_op:
            batch_op.add_column(sa.Column("retry_policy", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sources") as batch_op:
        batch_op.drop_column("retry_policy")
