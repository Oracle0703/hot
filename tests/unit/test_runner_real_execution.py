import os
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select

from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.job import CollectionJob
from app.models.job_log import JobLog
from app.models.source import Source
from app.services.job_service import JobService
from app.services.source_execution_service import SourceExecutionService
from app.collectors.registry import CollectorRegistry
from app.workers.runner import JobRunner


def make_database_url(tmp_path: Path, name: str) -> str:
    return f"sqlite:///{(tmp_path / name).as_posix()}"


HTML_SOURCE = """
<html>
  <body>
    <ul class='topics'>
      <li class='topic'>
        <a class='topic-link' href='https://example.com/post-1'>重磅新游版号过审</a>
        <span class='topic-time'>2026-03-24 08:00</span>
      </li>
    </ul>
  </body>
</html>
""".strip()


def test_runner_can_use_real_source_execution_service(tmp_path) -> None:
    html_path = tmp_path / "topics.html"
    html_path.write_text(HTML_SOURCE, encoding="utf-8")

    os.environ["DATABASE_URL"] = make_database_url(tmp_path, "runner-real.db")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory()

    with session_factory() as session:
        session.add(
            Source(
                name="本地 HTML",
                site_name="Local",
                entry_url=html_path.resolve().as_uri(),
                fetch_mode="http",
                parser_type="generic_css",
                list_selector=".topic",
                title_selector=".topic-link",
                link_selector=".topic-link",
                meta_selector=".topic-time",
                include_keywords=["新游"],
                exclude_keywords=[],
                max_items=10,
                enabled=True,
            )
        )
        session.commit()
        JobService(session).create_manual_job()

    execution_service = SourceExecutionService(CollectorRegistry())
    runner = JobRunner(session_factory=session_factory, source_executor=execution_service.execute)

    runner.run_once()

    with session_factory() as session:
        job = session.scalar(select(CollectionJob))
        logs = list(session.scalars(select(JobLog)).all())
        assert job.status == "success"
        assert job.success_sources == 1
        assert job.failed_sources == 0
        assert logs == []


def test_job_runner_builds_account_scoped_circuit_breaker_bucket(tmp_path) -> None:
    os.environ["DATABASE_URL"] = make_database_url(tmp_path, "runner-bucket.db")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory()
    runner = JobRunner(session_factory=session_factory, source_executor=lambda source: {"item_count": 0, "items": []})

    bucket = runner._build_circuit_breaker_bucket(
        SimpleNamespace(site_name="Bilibili", account_key="creator-a", entry_url="https://space.bilibili.com/20411266")
    )

    assert bucket == "bilibili:creator-a"
