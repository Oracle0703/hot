from __future__ import annotations

from pathlib import Path

from app.db import create_session_factory, get_engine
from app.models.base import Base
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
