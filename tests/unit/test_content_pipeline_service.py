from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.content_item import ContentItem
from app.models.raw_item import RawItem
from app.models.source import Source
from app.services.content_pipeline_service import ContentPipelineService
from app.services.job_service import JobService


def setup_database(tmp_path: Path, name: str):
    import os

    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / name).as_posix()}"
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory()


def test_pipeline_promotes_raw_items_into_content_items(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "content-pipeline.db")

    with session_factory() as session:
        source = Source(
            name="来源A",
            site_name="Example",
            entry_url="https://example.com/source",
            fetch_mode="http",
            parser_type="generic_css",
            max_items=30,
            enabled=True,
        )
        session.add(source)
        session.commit()
        session.refresh(source)
        job = JobService(session).create_manual_job()

        pipeline = ContentPipelineService(session)
        created = pipeline.ingest_run(
            job.id,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [{"title": "校招信息", "url": "https://example.com/a"}],
                }
            ],
        )

        raw_items = list(session.scalars(select(RawItem)).all())
        content_items = list(session.scalars(select(ContentItem)).all())

        assert created.raw_count == 1
        assert created.content_count == 1
        assert len(raw_items) == 1
        assert len(content_items) == 1
        assert content_items[0].canonical_url == "https://example.com/a"


def test_pipeline_deduplicates_content_items_across_runs(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "content-pipeline-dedupe.db")

    with session_factory() as session:
        source = Source(
            name="来源A",
            site_name="Example",
            entry_url="https://example.com/source",
            fetch_mode="http",
            parser_type="generic_css",
            max_items=30,
            enabled=True,
        )
        session.add(source)
        session.commit()
        session.refresh(source)
        first_job = JobService(session).create_manual_job()
        second_job = JobService(session).create_manual_job()
        pipeline = ContentPipelineService(session)

        first_result = pipeline.ingest_run(
            first_job.id,
            [{"source_id": source.id, "source_name": source.name, "items": [{"title": "校招信息", "url": "https://example.com/a"}]}],
        )
        second_result = pipeline.ingest_run(
            second_job.id,
            [{"source_id": source.id, "source_name": source.name, "items": [{"title": "校招信息-更新", "url": "https://example.com/a"}]}],
        )

        content_items = list(session.scalars(select(ContentItem)).all())

        assert first_result.content_count == 1
        assert second_result.content_count == 0
        assert len(content_items) == 1
        assert content_items[0].title == "校招信息-更新"
