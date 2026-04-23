from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path

from sqlalchemy import select

from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.job import CollectionJob
from app.services.scheduler_loop import SchedulerLoop
from app.services.scheduler_service import SchedulerService


class DummyDispatcher:
    def __init__(self) -> None:
        self.dispatch_count = 0

    def dispatch_pending_jobs(self) -> None:
        self.dispatch_count += 1


def setup_database(tmp_path: Path, name: str):
    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / name).as_posix()}"
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory()


def test_scheduler_loop_dispatches_job_when_due(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "scheduler-loop-due.db")
    dispatcher = DummyDispatcher()

    with session_factory() as session:
        SchedulerService(session).update_settings(enabled=True, daily_time="08:00")

    loop = SchedulerLoop(
        session_factory=session_factory,
        job_dispatcher=dispatcher,
        poll_interval_seconds=1,
        clock=lambda: datetime(2026, 3, 24, 8, 0, 0),
    )

    created_job = loop.run_once()

    with session_factory() as session:
        jobs = list(session.scalars(select(CollectionJob)).all())

    assert created_job is not None
    assert dispatcher.dispatch_count == 1
    assert len(jobs) == 1
    assert jobs[0].trigger_type == "scheduled"


def test_scheduler_loop_skips_dispatch_when_not_due(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "scheduler-loop-skip.db")
    dispatcher = DummyDispatcher()

    with session_factory() as session:
        SchedulerService(session).update_settings(enabled=True, daily_time="08:00")

    loop = SchedulerLoop(
        session_factory=session_factory,
        job_dispatcher=dispatcher,
        poll_interval_seconds=1,
        clock=lambda: datetime(2026, 3, 24, 7, 59, 0),
    )

    created_job = loop.run_once()

    with session_factory() as session:
        jobs = list(session.scalars(select(CollectionJob)).all())

    assert created_job is None
    assert dispatcher.dispatch_count == 0
    assert jobs == []
