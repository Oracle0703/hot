from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.source import Source
from app.schemas.source import SourceCreate
from app.services.source_service import SourceService


def setup_database(tmp_path: Path, name: str, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / name).as_posix()}")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory(engine=engine)


def test_create_app_reuses_same_engine_for_schema_and_sessions(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'app-engine-reuse.db').as_posix()}")
    monkeypatch.setenv("ENABLE_SCHEDULER", "0")
    import app.main as main_module

    sentinel_engine = object()
    schema_init_engines: list[object] = []
    session_factory_engines: list[object | None] = []

    monkeypatch.setattr(main_module, "get_engine", lambda: sentinel_engine)
    monkeypatch.setattr(main_module.Base.metadata, "create_all", lambda *, bind: schema_init_engines.append(bind))

    def fake_create_session_factory(engine=None):
        session_factory_engines.append(engine)
        return lambda: None

    monkeypatch.setattr(main_module, "create_session_factory", fake_create_session_factory)

    app = main_module.create_app(start_background_workers=False)
    with TestClient(app):
        pass

    assert schema_init_engines == [sentinel_engine]
    assert session_factory_engines == [sentinel_engine]


def test_create_app_runs_schema_init_in_lifespan_not_constructor(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'app-lifecycle.db').as_posix()}")
    monkeypatch.setenv("ENABLE_SCHEDULER", "0")
    from app.main import create_app

    calls = []

    def fake_create_all(*, bind) -> None:
        calls.append(bind)

    monkeypatch.setattr(Base.metadata, "create_all", fake_create_all)

    app = create_app(start_background_workers=False)
    assert calls == []

    with TestClient(app):
        pass

    assert len(calls) == 1


def test_seed_default_sources_inserts_two_records_on_empty_database(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "seed-defaults.db", monkeypatch)

    with session_factory() as session:
        service = SourceService(session)
        service.seed_default_sources()
        sources = list(session.scalars(select(Source)).all())

    source_map = {source.name: source for source in sources}
    assert set(source_map) == {"YouTube-ElectronicArts", "YouTube-EpicGames"}
    assert source_map["YouTube-ElectronicArts"].entry_url == "https://www.youtube.com/@ElectronicArts"
    assert source_map["YouTube-ElectronicArts"].collection_strategy == "youtube_channel_recent"
    assert source_map["YouTube-ElectronicArts"].search_keyword is None
    assert source_map["YouTube-EpicGames"].entry_url == "https://www.youtube.com/@EpicGamesStore"
    assert source_map["YouTube-EpicGames"].collection_strategy == "youtube_channel_recent"
    assert source_map["YouTube-EpicGames"].search_keyword is None


def test_seed_default_sources_is_idempotent(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "seed-idempotent.db", monkeypatch)

    with session_factory() as session:
        service = SourceService(session)
        service.seed_default_sources()
        service.seed_default_sources()
        source_count = session.scalar(select(func.count()).select_from(Source))

    assert source_count == 2


def test_seed_default_sources_does_not_override_existing_source_with_same_name(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "seed-existing-same-name.db", monkeypatch)

    with session_factory() as session:
        service = SourceService(session)
        existing = service.create_source(
            SourceCreate(
                name="YouTube-ElectronicArts",
                site_name="Custom Site",
                entry_url="https://example.com/custom",
                fetch_mode="http",
                parser_type="generic_css",
                list_selector=".custom-item",
                title_selector=".custom-title",
                link_selector=".custom-link",
                meta_selector=".custom-meta",
                include_keywords=["custom"],
                exclude_keywords=["ignore"],
                max_items=12,
                enabled=False,
                collection_strategy="generic_css",
                search_keyword="自定义关键词",
            )
        )

        service.seed_default_sources()
        source_count = session.scalar(select(func.count()).select_from(Source))
        preserved = session.get(Source, existing.id)

    assert source_count == 2
    assert preserved is not None
    assert preserved.entry_url == "https://example.com/custom"
    assert preserved.fetch_mode == "http"
    assert preserved.collection_strategy == "generic_css"
    assert preserved.search_keyword == "自定义关键词"

def test_create_app_upgrades_legacy_sqlite_sources_table_during_startup(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "legacy-startup.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("ENABLE_SCHEDULER", "0")

    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            CREATE TABLE sources (
                id CHAR(32) PRIMARY KEY NOT NULL,
                name VARCHAR(100) NOT NULL,
                site_name VARCHAR(100),
                entry_url TEXT NOT NULL,
                fetch_mode VARCHAR(20) NOT NULL,
                parser_type VARCHAR(50),
                max_items INTEGER NOT NULL,
                enabled BOOLEAN NOT NULL
            )
            """
        )
        connection.commit()
    finally:
        connection.close()

    from app.main import create_app

    with TestClient(create_app()):
        pass

    connection = sqlite3.connect(database_path)
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(sources)")}
        source_count = connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    finally:
        connection.close()

    assert {
        "list_selector",
        "title_selector",
        "link_selector",
        "meta_selector",
        "include_keywords",
        "exclude_keywords",
        "collection_strategy",
        "search_keyword",
    }.issubset(columns)
    assert source_count == 2

def test_seed_default_sources_updates_legacy_epicgames_url(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "seed-legacy-epicgames.db", monkeypatch)

    with session_factory() as session:
        session.add(
            Source(
                name="YouTube-EpicGames",
                site_name="YouTube",
                entry_url="https://www.youtube.com/@EpicGames",
                fetch_mode="playwright",
                collection_strategy="youtube_channel_recent",
                max_items=30,
                enabled=True,
            )
        )
        session.commit()

        service = SourceService(session)
        service.seed_default_sources()
        source = session.scalar(select(Source).where(Source.name == "YouTube-EpicGames"))

    assert source is not None
    assert source.entry_url == "https://www.youtube.com/@EpicGamesStore"


def test_seed_default_sources_removes_legacy_bilibili_default_source(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "seed-legacy-bilibili.db", monkeypatch)

    with session_factory() as session:
        service = SourceService(session)
        legacy_source = service.create_source(
            SourceCreate(
                name="B站-游戏-今日搜索",
                site_name="Bilibili",
                entry_url="https://www.bilibili.com/",
                fetch_mode="playwright",
                max_items=30,
                enabled=True,
                source_group="domestic",
                collection_strategy="bilibili_site_search",
                search_keyword="游戏",
            )
        )

        created_count = service.seed_default_sources()
        source_count = session.scalar(select(func.count()).select_from(Source))
        removed_source = session.get(Source, legacy_source.id)

    assert created_count == 2
    assert source_count == 2
    assert removed_source is None
