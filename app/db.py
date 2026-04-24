from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@dataclass(slots=True)
class DatabaseConfig:
    url: str
    driver: str


_SQLITE_LEGACY_SOURCE_COLUMN_PATCHES: tuple[tuple[str, str], ...] = (
    ("list_selector", "ALTER TABLE sources ADD COLUMN list_selector VARCHAR(200)"),
    ("title_selector", "ALTER TABLE sources ADD COLUMN title_selector VARCHAR(200)"),
    ("link_selector", "ALTER TABLE sources ADD COLUMN link_selector VARCHAR(200)"),
    ("meta_selector", "ALTER TABLE sources ADD COLUMN meta_selector VARCHAR(200)"),
    ("include_keywords", "ALTER TABLE sources ADD COLUMN include_keywords JSON NOT NULL DEFAULT '[]'"),
    ("exclude_keywords", "ALTER TABLE sources ADD COLUMN exclude_keywords JSON NOT NULL DEFAULT '[]'"),
    (
        "collection_strategy",
        "ALTER TABLE sources ADD COLUMN collection_strategy VARCHAR(50) NOT NULL DEFAULT 'generic_css'",
    ),
    ("source_group", "ALTER TABLE sources ADD COLUMN source_group VARCHAR(20)"),
    ("schedule_group", "ALTER TABLE sources ADD COLUMN schedule_group VARCHAR(100)"),
    ("search_keyword", "ALTER TABLE sources ADD COLUMN search_keyword VARCHAR(200)"),
    ("retry_policy", "ALTER TABLE sources ADD COLUMN retry_policy JSON"),
)


_SQLITE_LEGACY_COLLECTION_JOB_COLUMN_PATCHES: tuple[tuple[str, str], ...] = (
    ("source_group_scope", "ALTER TABLE collection_jobs ADD COLUMN source_group_scope VARCHAR(20)"),
    ("schedule_group_scope", "ALTER TABLE collection_jobs ADD COLUMN schedule_group_scope VARCHAR(100)"),
)


_SQLITE_LEGACY_COLLECTED_ITEM_COLUMN_PATCHES: tuple[tuple[str, str], ...] = (
    ("author", "ALTER TABLE collected_items ADD COLUMN author VARCHAR(100)"),
    ("first_seen_job_id", "ALTER TABLE collected_items ADD COLUMN first_seen_job_id CHAR(32)"),
    ("last_seen_job_id", "ALTER TABLE collected_items ADD COLUMN last_seen_job_id CHAR(32)"),
    ("first_seen_at", "ALTER TABLE collected_items ADD COLUMN first_seen_at DATETIME"),
    ("last_seen_at", "ALTER TABLE collected_items ADD COLUMN last_seen_at DATETIME"),
    ("published_at_text", "ALTER TABLE collected_items ADD COLUMN published_at_text VARCHAR(100)"),
    ("cover_image_url", "ALTER TABLE collected_items ADD COLUMN cover_image_url TEXT"),
    ("like_count", "ALTER TABLE collected_items ADD COLUMN like_count INTEGER"),
    ("reply_count", "ALTER TABLE collected_items ADD COLUMN reply_count INTEGER"),
    ("view_count", "ALTER TABLE collected_items ADD COLUMN view_count INTEGER"),
    ("recommended_grade", "ALTER TABLE collected_items ADD COLUMN recommended_grade VARCHAR(10)"),
    ("manual_grade", "ALTER TABLE collected_items ADD COLUMN manual_grade VARCHAR(10)"),
    ("pushed_to_dingtalk_at", "ALTER TABLE collected_items ADD COLUMN pushed_to_dingtalk_at DATETIME"),
    ("pushed_to_dingtalk_batch_id", "ALTER TABLE collected_items ADD COLUMN pushed_to_dingtalk_batch_id VARCHAR(64)"),
    ("image_urls", "ALTER TABLE collected_items ADD COLUMN image_urls JSON NOT NULL DEFAULT '[]'"),
)


def detect_database_driver(database_url: str) -> str:
    if database_url.startswith("mysql"):
        return "mysql"
    if database_url.startswith("sqlite"):
        return "sqlite"
    return "unknown"


def get_database_config() -> DatabaseConfig:
    settings = get_settings()
    return DatabaseConfig(
        url=settings.database_url,
        driver=detect_database_driver(settings.database_url),
    )


def get_reports_root() -> Path:
    reports_root = Path(get_settings().reports_root)
    reports_root.mkdir(parents=True, exist_ok=True)
    return reports_root


def _ensure_sqlite_directory(database_url: str) -> None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return

    database_path = database_url.removeprefix(prefix)
    if database_path == ":memory:" or not database_path:
        return

    Path(database_path).parent.mkdir(parents=True, exist_ok=True)


def _collect_missing_column_statements(
    inspector,
    table_name: str,
    column_patches: tuple[tuple[str, str], ...],
) -> list[str]:
    if table_name not in inspector.get_table_names():
        return []

    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    return [statement for column_name, statement in column_patches if column_name not in existing_columns]


def ensure_schema_compatibility(engine: Engine) -> None:
    if not hasattr(engine, "dialect") or engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    pending_statements = [
        *_collect_missing_column_statements(inspector, "sources", _SQLITE_LEGACY_SOURCE_COLUMN_PATCHES),
        *_collect_missing_column_statements(inspector, "collection_jobs", _SQLITE_LEGACY_COLLECTION_JOB_COLUMN_PATCHES),
        *_collect_missing_column_statements(
            inspector,
            "collected_items",
            _SQLITE_LEGACY_COLLECTED_ITEM_COLUMN_PATCHES,
        ),
    ]
    if not pending_statements:
        return

    with engine.begin() as connection:
        for statement in pending_statements:
            connection.execute(text(statement))


def get_engine() -> Engine:
    database_config = get_database_config()
    if database_config.driver == "sqlite":
        _ensure_sqlite_directory(database_config.url)

    connect_args = {"check_same_thread": False} if database_config.driver == "sqlite" else {}
    return create_engine(database_config.url, future=True, connect_args=connect_args)


def create_session_factory(engine: Engine | None = None) -> sessionmaker:
    bind_engine = engine or get_engine()
    return sessionmaker(bind=bind_engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session(session_factory: sessionmaker) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()

