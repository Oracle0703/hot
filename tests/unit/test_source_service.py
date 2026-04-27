from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, inspect, text

from app.db import create_session_factory, ensure_schema_compatibility, get_engine
from app.models.base import Base
from app.models.site_account import SiteAccount
from app.models.source import Source
from app.services.source_service import SourceService


def make_database_url(tmp_path: Path, name: str) -> str:
    return f"sqlite:///{(tmp_path / name).as_posix()}"


def setup_database(tmp_path: Path, name: str):
    import os

    os.environ["DATABASE_URL"] = make_database_url(tmp_path, name)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory(engine=engine)


def test_source_service_counts_enabled_sources_by_group(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "source-service-group.db")
    with session_factory() as session:
        session.add(
            Source(
                name="国内来源",
                site_name="NGA",
                entry_url="https://example.com/domestic",
                fetch_mode="http",
                parser_type="generic_css",
                max_items=30,
                enabled=True,
                source_group="domestic",
            )
        )
        session.add(
            Source(
                name="国外来源",
                site_name="YouTube",
                entry_url="https://example.com/overseas",
                fetch_mode="http",
                parser_type="generic_css",
                max_items=30,
                enabled=True,
                source_group="overseas",
            )
        )
        session.add(
            Source(
                name="未分组来源",
                site_name="Local",
                entry_url="https://example.com/unset",
                fetch_mode="http",
                parser_type="generic_css",
                max_items=30,
                enabled=True,
            )
        )
        session.commit()

        service = SourceService(session)

        assert service.count_enabled_sources("domestic") == 1
        assert service.count_enabled_sources("overseas") == 1
        assert len(service.list_sources_by_group(None)) == 1


def test_source_service_gets_source_by_id(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "source-service-get.db")
    with session_factory() as session:
        created = Source(
            name="国内来源",
            site_name="NGA",
            entry_url="https://example.com/domestic",
            fetch_mode="http",
            parser_type="generic_css",
            max_items=30,
            enabled=True,
            source_group="domestic",
        )
        session.add(created)
        session.commit()

        service = SourceService(session)

        source = service.get_source(str(created.id))

        assert source is not None
        assert source.id == created.id
        assert source.name == "国内来源"


def test_ensure_schema_compatibility_adds_retry_policy_column_for_legacy_sources_table(tmp_path) -> None:
    url = make_database_url(tmp_path, "legacy-source-schema.db")
    engine = create_engine(url, future=True)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE sources (
                    id CHAR(32) PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    site_name VARCHAR(100),
                    entry_url TEXT NOT NULL,
                    fetch_mode VARCHAR(20) NOT NULL,
                    parser_type VARCHAR(50),
                    list_selector VARCHAR(200),
                    title_selector VARCHAR(200),
                    link_selector VARCHAR(200),
                    meta_selector VARCHAR(200),
                    include_keywords JSON NOT NULL DEFAULT '[]',
                    exclude_keywords JSON NOT NULL DEFAULT '[]',
                    max_items INTEGER NOT NULL DEFAULT 30,
                    enabled BOOLEAN NOT NULL DEFAULT 1,
                    source_group VARCHAR(20),
                    schedule_group VARCHAR(100),
                    collection_strategy VARCHAR(50) NOT NULL DEFAULT 'generic_css',
                    search_keyword VARCHAR(200)
                )
                """
            )
        )

    ensure_schema_compatibility(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("sources")}
    assert "retry_policy" in columns
    assert "account_id" in columns


def test_source_service_create_source_rejects_disabled_account_id(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "source-service-disabled-account.db")
    with session_factory() as session:
        account = SiteAccount(
            platform="bilibili",
            account_key="creator-a",
            display_name="账号A",
            enabled=False,
            is_default=False,
        )
        session.add(account)
        session.commit()
        service = SourceService(session)

        payload = SimpleNamespace(
            model_dump=lambda **kwargs: {
                "name": "B站UP",
                "site_name": "Bilibili",
                "entry_url": "https://space.bilibili.com/20411266",
                "fetch_mode": "playwright",
                "parser_type": None,
                "include_keywords": [],
                "exclude_keywords": [],
                "max_items": 30,
                "enabled": True,
                "source_group": "domestic",
                "schedule_group": None,
                "collection_strategy": "bilibili_profile_videos_recent",
                "search_keyword": None,
                "account_id": account.id,
            }
        )

        with pytest.raises(ValueError, match="disabled|禁用"):
            service.create_source(payload)
