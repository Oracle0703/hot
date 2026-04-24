"""Alembic environment for HotCollector.

主要逻辑:
- 优先从 `app.config.get_settings().database_url` 读取连接串(避免 alembic.ini 与运行时分裂)。
- target_metadata = `app.models.base.Base.metadata`,支持 autogenerate(开发期辅助)。
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# 让 `app` 包可被 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.models  # noqa: F401  -- 触发模型注册
from app.config import get_settings
from app.models.base import Base

config = context.config
if config.config_file_name is not None:
    # disable_existing_loggers=False 防止破坏 pytest caplog 等已存在 logger
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# 仅当配置(alembic.ini 或 set_main_option)未指定时，回退到运行期 settings
existing_url = config.get_main_option("sqlalchemy.url") or ""
if not existing_url:
    runtime_url = os.getenv("DATABASE_URL") or get_settings().database_url
    config.set_main_option("sqlalchemy.url", runtime_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
