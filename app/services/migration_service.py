"""阶段 3.1 — Alembic 迁移服务(REQ-MIG-001)。

提供统一入口 `run_migrations`:
* 启动时根据环境变量 `AUTO_MIGRATE`(默认 true)决定是否自动 upgrade。
* 升级前若检测到待执行迁移,会自动产出一个 SQLite 备份到 `data/backups/`。
* 旧库(已经存在业务表但无 alembic_version)自动 stamp 到 head,避免重复建表。
"""
from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger("app.migrations")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


@dataclass(slots=True)
class MigrationResult:
    action: str  # "upgrade_head" | "stamp_head" | "skipped" | "noop"
    backup_path: Optional[Path] = None
    pending_revisions: tuple[str, ...] = ()


def _build_alembic_config(database_url: str, *, ini_path: Path = DEFAULT_ALEMBIC_INI) -> Config:
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def _is_auto_migrate_enabled() -> bool:
    raw = os.getenv("AUTO_MIGRATE")
    if raw is None:
        return True
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _current_revision(engine: Engine) -> Optional[str]:
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        return ctx.get_current_revision()


def _has_business_tables(engine: Engine) -> bool:
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    return bool(tables - {"alembic_version"})


def _list_pending_revisions(cfg: Config, engine: Engine) -> tuple[str, ...]:
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    current = _current_revision(engine)
    if head is None or current == head:
        return ()
    revs: list[str] = []
    for rev in script.walk_revisions():
        if rev.revision == current:
            break
        revs.append(rev.revision)
    return tuple(reversed(revs))


def _backup_sqlite_database(database_url: str, backup_dir: Path) -> Optional[Path]:
    if not database_url.startswith("sqlite"):
        return None
    # sqlite:///./data/hot_topics.db   或   sqlite:///C:/path/to/db
    raw = database_url.split("sqlite:///", 1)[-1]
    db_path = Path(raw)
    if not db_path.is_absolute():
        db_path = (PROJECT_ROOT / db_path).resolve()
    if not db_path.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"auto-pre-migrate-{ts}.db"
    shutil.copy2(db_path, target)
    return target


def run_migrations(
    engine: Engine,
    database_url: str,
    *,
    auto_migrate: bool | None = None,
    backup_dir: Path | None = None,
    ini_path: Path = DEFAULT_ALEMBIC_INI,
) -> MigrationResult:
    """根据当前 DB 状态执行合适的迁移动作。"""
    enabled = _is_auto_migrate_enabled() if auto_migrate is None else auto_migrate
    if not enabled:
        logger.warning("AUTO_MIGRATE_DISABLED 已禁用自动迁移,跳过 upgrade。")
        return MigrationResult(action="skipped")

    backup_dir = backup_dir or (PROJECT_ROOT / "data" / "backups")
    cfg = _build_alembic_config(database_url, ini_path=ini_path)

    current = _current_revision(engine)
    has_business = _has_business_tables(engine)

    if current is None and has_business:
        # 旧库 — 直接 stamp 到 head,避免重复建表
        command.stamp(cfg, "head")
        logger.info("LEGACY_DB_STAMPED 已对存量数据库标记为最新版本(stamp head)。")
        return MigrationResult(action="stamp_head")

    pending = _list_pending_revisions(cfg, engine)
    if not pending and current is not None:
        return MigrationResult(action="noop")

    backup_path: Optional[Path] = None
    if pending:
        backup_path = _backup_sqlite_database(database_url, backup_dir)

    command.upgrade(cfg, "head")
    return MigrationResult(action="upgrade_head", backup_path=backup_path, pending_revisions=pending)
