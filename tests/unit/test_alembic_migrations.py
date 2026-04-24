"""TC-MIG-001~005 — Alembic 迁移单元测试。"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from app.services.migration_service import run_migrations


def _sqlite_url(tmp_path: Path, name: str = "mig.db") -> str:
    return f"sqlite:///{(tmp_path / name).as_posix()}"


def test_upgrade_head_creates_baseline_on_empty_db(tmp_path) -> None:
    """TC-MIG-001"""
    url = _sqlite_url(tmp_path)
    engine = create_engine(url)
    result = run_migrations(engine, url, backup_dir=tmp_path / "backups")
    assert result.action == "upgrade_head"
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    # alembic 与若干核心业务表
    assert "alembic_version" in tables
    for required in ("sources", "collection_jobs", "collected_items", "job_logs"):
        assert required in tables, required


def test_upgrade_head_preserves_legacy_data(tmp_path) -> None:
    """TC-MIG-002 — 旧库已经有业务表但无 alembic_version,应 stamp 而不是重建"""
    url = _sqlite_url(tmp_path, "legacy.db")
    engine = create_engine(url)
    # 用 metadata.create_all 模拟旧库
    import app.models  # noqa: F401
    from app.models.base import Base

    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO sources (id, name, entry_url, enabled, fetch_mode, collection_strategy, "
            "include_keywords, exclude_keywords, max_items) "
            "VALUES ('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'legacy', 'https://example.com', 1, 'http', "
            "'generic_css', '[]', '[]', 30)"
        ))

    result = run_migrations(engine, url, backup_dir=tmp_path / "backups")
    assert result.action == "stamp_head"
    with engine.begin() as conn:
        row = conn.execute(text("SELECT name FROM sources WHERE name='legacy'")).fetchone()
    assert row is not None and row[0] == "legacy"


def test_downgrade_one_revision_is_executable(tmp_path) -> None:
    """TC-MIG-003 — 升级后再 downgrade base 应成功"""
    url = _sqlite_url(tmp_path)
    engine = create_engine(url)
    run_migrations(engine, url, backup_dir=tmp_path / "backups")
    from alembic import command
    from app.services.migration_service import _build_alembic_config

    cfg = _build_alembic_config(url)
    command.downgrade(cfg, "base")
    insp = inspect(engine)
    assert "sources" not in inspect(create_engine(url)).get_table_names()


def test_auto_migrate_disable_skips(tmp_path, monkeypatch) -> None:
    """TC-MIG-004"""
    url = _sqlite_url(tmp_path)
    engine = create_engine(url)
    monkeypatch.setenv("AUTO_MIGRATE", "false")
    result = run_migrations(engine, url, backup_dir=tmp_path / "backups")
    assert result.action == "skipped"
    insp = inspect(engine)
    assert "sources" not in insp.get_table_names()


def test_pre_migrate_backup_created(tmp_path) -> None:
    """TC-MIG-005 — 第一次 upgrade 不会备份(库还不存在),因此先 upgrade 一次再 downgrade 制造 pending,
    再 upgrade 应触发备份。"""
    url = _sqlite_url(tmp_path, "with-data.db")
    engine = create_engine(url)
    backup_dir = tmp_path / "backups"

    run_migrations(engine, url, backup_dir=backup_dir)  # 首次 upgrade -> 创建 db
    # 此时 db 文件存在,downgrade 制造 pending
    from alembic import command
    from app.services.migration_service import _build_alembic_config

    cfg = _build_alembic_config(url)
    command.downgrade(cfg, "base")
    # downgrade 后 db 文件仍在(只是表被 drop),再次 upgrade 应触发备份
    result = run_migrations(engine, url, backup_dir=backup_dir)
    assert result.action == "upgrade_head"
    assert result.backup_path is not None and result.backup_path.exists()
    assert result.backup_path.name.startswith("auto-pre-migrate-")
