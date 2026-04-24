"""baseline schema

Revision ID: 0001_baseline
Revises:
Create Date: 2026-04-23

策略:复用 SQLAlchemy 模型元数据一次性建表/拆表。后续迁移以增量 ALTER 形式追加。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa  # noqa: F401  -- alembic 模板要求


revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 延迟导入,避免 alembic env 加载顺序问题
    import app.models  # noqa: F401
    from app.models.base import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    import app.models  # noqa: F401
    from app.models.base import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
