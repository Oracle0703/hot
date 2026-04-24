from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path

from sqlalchemy import select

from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.job import CollectionJob
from app.models.scheduler_setting import SchedulerSetting
from app.models.schedule_plan import SchedulePlan
from app.models.source import Source
from app.services.scheduler_service import SchedulerService


def setup_database(tmp_path: Path, name: str):
    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / name).as_posix()}"
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory()


def create_enabled_source(session, *, name: str, schedule_group: str | None) -> None:
    session.add(
        Source(
            name=name,
            site_name="Test",
            entry_url=f"https://example.com/{name}",
            fetch_mode="http",
            parser_type="generic_css",
            max_items=30,
            enabled=True,
            schedule_group=schedule_group,
        )
    )
    session.commit()


def create_plan(session, *, run_time: str, schedule_group: str, enabled: bool = True) -> SchedulePlan:
    plan = SchedulePlan(enabled=enabled, run_time=run_time, schedule_group=schedule_group)
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def test_scheduler_service_creates_job_for_due_plan_once_per_day(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "scheduler-due.db")

    with session_factory() as session:
        create_enabled_source(session, name="morning-source", schedule_group="morning")
        create_plan(session, run_time="08:00", schedule_group="morning")
        service = SchedulerService(session)
        service.update_settings(enabled=True, daily_time="08:00")

        created_jobs = service.run_due_jobs(datetime(2026, 3, 24, 8, 0, 0))
        jobs = list(session.scalars(select(CollectionJob)).all())

    assert len(created_jobs) == 1
    assert len(jobs) == 1
    assert jobs[0].trigger_type == "scheduled"
    assert jobs[0].status == "pending"
    assert jobs[0].schedule_group_scope == "morning"


def test_scheduler_service_does_not_create_duplicate_job_on_same_day(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "scheduler-once.db")

    with session_factory() as session:
        create_enabled_source(session, name="morning-source", schedule_group="morning")
        create_plan(session, run_time="08:00", schedule_group="morning")
        service = SchedulerService(session)
        service.update_settings(enabled=True, daily_time="08:00")

        first_jobs = service.run_due_jobs(datetime(2026, 3, 24, 8, 0, 0))
        second_jobs = service.run_due_jobs(datetime(2026, 3, 24, 8, 5, 0))
        jobs = list(session.scalars(select(CollectionJob)).all())

    assert len(first_jobs) == 1
    assert second_jobs == []
    assert len(jobs) == 1


def test_scheduler_service_respects_disabled_setting(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "scheduler-disabled.db")

    with session_factory() as session:
        create_enabled_source(session, name="morning-source", schedule_group="morning")
        create_plan(session, run_time="08:00", schedule_group="morning")
        service = SchedulerService(session)
        service.update_settings(enabled=False, daily_time="08:00")

        created_jobs = service.run_due_jobs(datetime(2026, 3, 24, 8, 0, 0))
        jobs = list(session.scalars(select(CollectionJob)).all())

    assert created_jobs == []
    assert jobs == []


def test_scheduler_service_skips_plan_without_enabled_sources(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "scheduler-no-sources.db")

    with session_factory() as session:
        plan = create_plan(session, run_time="08:00", schedule_group="morning")
        service = SchedulerService(session)
        service.update_settings(enabled=True, daily_time="08:00")

        created_jobs = service.run_due_jobs(datetime(2026, 3, 24, 8, 0, 0))
        jobs = list(session.scalars(select(CollectionJob)).all())
        refreshed_plan = session.get(SchedulePlan, plan.id)

    assert created_jobs == []
    assert jobs == []
    assert refreshed_plan is not None
    assert refreshed_plan.last_triggered_on is None


def test_scheduler_service_allows_same_group_to_run_at_multiple_times(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "scheduler-multi-plan.db")

    with session_factory() as session:
        create_enabled_source(session, name="morning-source", schedule_group="morning")
        create_plan(session, run_time="08:00", schedule_group="morning")
        create_plan(session, run_time="18:00", schedule_group="morning")
        service = SchedulerService(session)
        service.update_settings(enabled=True, daily_time="08:00")

        first_jobs = service.run_due_jobs(datetime(2026, 3, 24, 8, 0, 0))
        second_jobs = service.run_due_jobs(datetime(2026, 3, 24, 18, 0, 0))
        jobs = list(session.scalars(select(CollectionJob).order_by(CollectionJob.id.asc())).all())

    assert len(first_jobs) == 1
    assert len(second_jobs) == 1
    assert len(jobs) == 2
    assert [job.schedule_group_scope for job in jobs] == ["morning", "morning"]


def test_scheduler_service_migrates_legacy_daily_time_to_default_plan(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "scheduler-legacy-default-plan.db")

    with session_factory() as session:
        session.add(SchedulerSetting(id=1, enabled=True, daily_time="09:30"))
        session.commit()

        settings = SchedulerService(session).get_settings()
        plans = list(session.scalars(select(SchedulePlan).order_by(SchedulePlan.id.asc())).all())

    assert settings.daily_time == "09:30"
    assert len(plans) == 1
    assert plans[0].run_time == "09:30"
    assert plans[0].schedule_group == "default"
