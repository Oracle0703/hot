from __future__ import annotations

from pathlib import Path

from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.source import Source
from app.services.job_service import JobService


def make_database_url(tmp_path: Path, name: str) -> str:
    return f"sqlite:///{(tmp_path / name).as_posix()}"


def setup_database(tmp_path: Path, name: str):
    import os

    os.environ["DATABASE_URL"] = make_database_url(tmp_path, name)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory(engine=engine)


def test_job_service_creates_manual_job_for_specific_group(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "job-service-group.db")
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
        session.commit()

        job = JobService(session).create_manual_job_for_group("domestic")

        assert job.total_sources == 1
        assert job.source_group_scope == "domestic"
