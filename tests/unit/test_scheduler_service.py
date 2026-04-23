from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path

from sqlalchemy import select

from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.job import CollectionJob
from app.services.scheduler_service import SchedulerService


def setup_database(tmp_path: Path, name: str):
    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / name).as_posix()}"
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory()


def test_scheduler_service_creates_scheduled_job_when_due(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "scheduler-due.db")

    with session_factory() as session:
        service = SchedulerService(session)
        service.update_settings(enabled=True, daily_time="08:00")
        created_job = service.run_due_jobs(datetime(2026, 3, 24, 8, 0, 0))
        jobs = list(session.scalars(select(CollectionJob)).all())

    assert created_job is not None
    assert len(jobs) == 1
    assert jobs[0].trigger_type == "scheduled"
    assert jobs[0].status == "pending"


def test_scheduler_service_does_not_create_duplicate_job_on_same_day(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "scheduler-once.db")

    with session_factory() as session:
        service = SchedulerService(session)
        service.update_settings(enabled=True, daily_time="08:00")
        first_job = service.run_due_jobs(datetime(2026, 3, 24, 8, 0, 0))
        second_job = service.run_due_jobs(datetime(2026, 3, 24, 8, 5, 0))
        jobs = list(session.scalars(select(CollectionJob)).all())

    assert first_job is not None
    assert second_job is None
    assert len(jobs) == 1


def test_scheduler_service_respects_disabled_setting(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "scheduler-disabled.db")

    with session_factory() as session:
        service = SchedulerService(session)
        service.update_settings(enabled=False, daily_time="08:00")
        created_job = service.run_due_jobs(datetime(2026, 3, 24, 8, 0, 0))
        jobs = list(session.scalars(select(CollectionJob)).all())

    assert created_job is None
    assert jobs == []
