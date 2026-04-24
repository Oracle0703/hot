from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import select

from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.job import CollectionJob
from app.models.job_log import JobLog
from app.models.source import Source
from app.services.dingtalk_webhook_service import DingTalkWebhookService
from app.services.job_service import JobService
from app.services.report_distribution_service import ReportDistributionService
from app.services.report_service import ReportService
from app.services.weekly_cover_cache_service import WeeklyCoverCacheService
from app.workers.runner import JobRunner


def make_database_url(tmp_path: Path, name: str) -> str:
    return f"sqlite:///{(tmp_path / name).as_posix()}"


def setup_database(tmp_path: Path, name: str):
    import os

    os.environ["HOT_RUNTIME_ROOT"] = str(tmp_path)
    os.environ["DATABASE_URL"] = make_database_url(tmp_path, name)
    os.environ["REPORTS_ROOT"] = str(tmp_path / "reports")
    os.environ["ENABLE_DINGTALK_NOTIFIER"] = "false"
    os.environ.pop("DINGTALK_WEBHOOK", None)
    os.environ.pop("DINGTALK_SECRET", None)
    os.environ.pop("DINGTALK_KEYWORD", None)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory()


def test_runner_returns_none_when_no_pending_job(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "runner-empty.db")
    runner = JobRunner(session_factory=session_factory, source_executor=lambda source: {"item_count": 0})

    result = runner.run_once()

    assert result is None


def test_runner_marks_job_success_when_all_sources_succeed(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "runner-success.db")
    monkeypatch.setenv("ENABLE_DINGTALK_NOTIFIER", "true")
    monkeypatch.setenv("DINGTALK_WEBHOOK", "https://oapi.dingtalk.com/robot/send?access_token=test-token")
    with session_factory() as session:
        session.add(Source(name="NGA", site_name="NGA", entry_url="https://example.com", fetch_mode="http", parser_type="generic_css", max_items=30, enabled=True))
        session.commit()
        job = JobService(session).create_manual_job()
        job_id = str(job.id)

    monkeypatch.setattr(DingTalkWebhookService, "_send_webhook", lambda self, webhook, payload, timeout_seconds, secret: None)

    runner = JobRunner(
        session_factory=session_factory,
        source_executor=lambda source: {
            "item_count": 1,
            "items": [
                {
                    "title": "新帖子",
                    "url": "https://example.com/post-new",
                    "published_at": "2026-03-24 10:00",
                }
            ],
        },
        notification_scheduler=lambda task: task(),
    )

    processed_job_id = runner.run_once()

    with session_factory() as session:
        job = session.get(CollectionJob, processed_job_id)
        logs = list(session.scalars(select(JobLog).where(JobLog.job_id == processed_job_id).order_by(JobLog.created_at.asc())).all())
        assert str(processed_job_id) == job_id
        assert job.status == "success"
        assert job.completed_sources == 1
        assert job.success_sources == 1
        assert job.failed_sources == 0
        assert job.started_at is not None
        assert job.finished_at is not None
        assert any(log.level == "info" and "dingtalk notification sent:" in log.message for log in logs)
        assert any(log.level == "info" and "1/1 source NGA" in log.message for log in logs)
        assert not any("summary" in log.message for log in logs)


def test_runner_logs_failure_and_marks_job_failed_when_source_executor_errors(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "runner-failure.db")
    with session_factory() as session:
        session.add(Source(name="NGA", site_name="NGA", entry_url="https://example.com", fetch_mode="http", parser_type="generic_css", max_items=30, enabled=True))
        session.commit()
        JobService(session).create_manual_job()

    def fail_executor(source: Source) -> dict[str, int]:
        raise RuntimeError("selector missing")

    runner = JobRunner(session_factory=session_factory, source_executor=fail_executor)

    runner.run_once()

    with session_factory() as session:
        job = session.scalar(select(CollectionJob))
        logs = list(session.scalars(select(JobLog)).all())
        assert job.status == "failed"
        assert job.completed_sources == 1
        assert job.success_sources == 0
        assert job.failed_sources == 1
        assert len(logs) == 1
        assert logs[0].level == "error"
        assert "selector missing" in logs[0].message


def test_runner_marks_job_failed_and_logs_error_when_report_generation_fails(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "runner-report-failure.db")
    with session_factory() as session:
        session.add(Source(name="NGA", site_name="NGA", entry_url="https://example.com", fetch_mode="http", parser_type="generic_css", max_items=30, enabled=True))
        session.commit()
        job = JobService(session).create_manual_job()
        job_id = job.id

    def fail_report_generation(self, job: CollectionJob, source_runs: list[dict[str, object]]) -> None:
        raise RuntimeError("report write failed")

    monkeypatch.setattr(ReportService, "generate_for_job", fail_report_generation)

    runner = JobRunner(
        session_factory=session_factory,
        source_executor=lambda source: {"item_count": 1, "items": []},
        notification_scheduler=lambda task: task(),
    )

    with pytest.raises(RuntimeError, match="report write failed"):
        runner.run_once()

    with session_factory() as session:
        job = session.get(CollectionJob, job_id)
        logs = list(session.scalars(select(JobLog).where(JobLog.job_id == job_id).order_by(JobLog.created_at.asc())).all())

        assert job is not None
        assert job.status == "failed"
        assert job.success_sources == 1
        assert job.failed_sources == 0
        assert any(log.level == "error" and "report generation failed: report write failed" in log.message for log in logs)

def test_runner_keeps_job_success_when_dingtalk_notification_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_DINGTALK_NOTIFIER", "true")
    monkeypatch.setenv("DINGTALK_WEBHOOK", "https://oapi.dingtalk.com/robot/send?access_token=test-token")
    session_factory = setup_database(tmp_path, "runner-dingtalk-failure.db")
    with session_factory() as session:
        session.add(Source(name="NGA", site_name="NGA", entry_url="https://example.com", fetch_mode="http", parser_type="generic_css", max_items=30, enabled=True))
        session.commit()
        job = JobService(session).create_manual_job()
        job_id = job.id

    def fail_notify(self, job: CollectionJob) -> bool:
        raise RuntimeError("dingtalk webhook failed")

    monkeypatch.setattr(DingTalkWebhookService, "notify_job_summary", fail_notify)

    runner = JobRunner(
        session_factory=session_factory,
        source_executor=lambda source: {"item_count": 1, "items": []},
        notification_scheduler=lambda task: task(),
    )

    processed_job_id = runner.run_once()

    with session_factory() as session:
        job = session.get(CollectionJob, job_id)
        logs = list(session.scalars(select(JobLog).where(JobLog.job_id == job_id).order_by(JobLog.created_at.asc())).all())

        assert processed_job_id == job_id
        assert job is not None
        assert job.status == "success"
        assert any(log.level == "warning" and "dingtalk notification failed: dingtalk webhook failed" in log.message for log in logs)




def test_runner_copies_report_to_share_dir_after_generation(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "runner-report-distribution.db")
    with session_factory() as session:
        session.add(Source(name="NGA", site_name="NGA", entry_url="https://example.com", fetch_mode="http", parser_type="generic_css", max_items=30, enabled=True))
        session.commit()
        JobService(session).create_manual_job()

    generated_report = object()
    copied: dict[str, object] = {"report": None}

    def fake_generate(self, job: CollectionJob, source_runs: list[dict[str, object]]) -> object:
        return generated_report

    def fake_copy(self, report: object) -> Path:
        copied["report"] = report
        return tmp_path / "shared-reports"

    monkeypatch.setattr(ReportService, "generate_for_job", fake_generate)
    monkeypatch.setattr(ReportDistributionService, "copy_report_to_share_dir", fake_copy)

    runner = JobRunner(
        session_factory=session_factory,
        source_executor=lambda source: {"item_count": 1, "items": []},
        notification_scheduler=lambda task: task(),
    )

    runner.run_once()

    assert copied["report"] is generated_report


def test_runner_prunes_weekly_cover_cache_using_configured_retention_days(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "runner-weekly-cover-prune.db")
    with session_factory() as session:
        session.add(Source(name="NGA", site_name="NGA", entry_url="https://example.com", fetch_mode="http", parser_type="generic_css", max_items=30, enabled=True))
        session.commit()
        JobService(session).create_manual_job()

    prune_calls: list[int] = []

    def fake_prune(self, *, now=None, max_age_days: int = 60) -> None:
        prune_calls.append(max_age_days)

    monkeypatch.setattr(WeeklyCoverCacheService, "prune", fake_prune)

    runner = JobRunner(
        session_factory=session_factory,
        source_executor=lambda source: {"item_count": 1, "items": []},
        notification_scheduler=lambda task: task(),
        settings_provider=lambda: SimpleNamespace(
            source_fetch_interval_seconds=0,
            bilibili_source_interval_seconds=0,
            weekly_cover_cache_retention_days=45,
        ),
    )

    runner.run_once()

    assert prune_calls == [45]

def test_runner_logs_warning_when_dingtalk_notification_is_skipped(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, 'runner-dingtalk-skipped.db')
    with session_factory() as session:
        session.add(Source(name='NGA', site_name='NGA', entry_url='https://example.com', fetch_mode='http', parser_type='generic_css', max_items=30, enabled=True))
        session.commit()
        job = JobService(session).create_manual_job()
        job_id = job.id

    monkeypatch.setattr(DingTalkWebhookService, 'notify_job_summary', lambda self, job: False)
    monkeypatch.setattr(DingTalkWebhookService, 'get_skip_reason', lambda self: 'ENABLE_DINGTALK_NOTIFIER is false', raising=False)

    runner = JobRunner(
        session_factory=session_factory,
        source_executor=lambda source: {'item_count': 1, 'items': []},
        notification_scheduler=lambda task: task(),
    )

    processed_job_id = runner.run_once()

    with session_factory() as session:
        job = session.get(CollectionJob, job_id)
        logs = list(session.scalars(select(JobLog).where(JobLog.job_id == job_id).order_by(JobLog.created_at.asc())).all())

        assert processed_job_id == job_id
        assert job is not None
        assert job.status == 'success'
        assert any(log.level == 'warning' and 'dingtalk notification skipped: ENABLE_DINGTALK_NOTIFIER is false' in log.message for log in logs)


def test_runner_executes_only_sources_in_job_scope(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "runner-group-scope.db")
    executed_names: list[str] = []
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
        job_id = job.id

    def record_executor(source: Source) -> dict[str, object]:
        executed_names.append(source.name)
        return {"item_count": 1, "items": []}

    runner = JobRunner(session_factory=session_factory, source_executor=record_executor)
    processed_job_id = runner.run_once()

    assert processed_job_id == job_id
    assert executed_names == ["国内来源"]


def test_runner_executes_only_sources_in_schedule_group_scope(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "runner-schedule-group-scope.db")
    executed_names: list[str] = []
    with session_factory() as session:
        session.add(
            Source(
                name="早报来源",
                site_name="Bilibili",
                entry_url="https://example.com/morning",
                fetch_mode="http",
                parser_type="generic_css",
                max_items=30,
                enabled=True,
                schedule_group="morning",
            )
        )
        session.add(
            Source(
                name="晚报来源",
                site_name="Bilibili",
                entry_url="https://example.com/evening",
                fetch_mode="http",
                parser_type="generic_css",
                max_items=30,
                enabled=True,
                schedule_group="evening",
            )
        )
        session.commit()
        job = JobService(session).create_manual_job_for_schedule_group("morning")
        job_id = job.id

    def record_executor(source: Source) -> dict[str, object]:
        executed_names.append(source.name)
        return {"item_count": 1, "items": []}

    runner = JobRunner(session_factory=session_factory, source_executor=record_executor)
    processed_job_id = runner.run_once()

    assert processed_job_id == job_id
    assert executed_names == ["早报来源"]


def test_runner_waits_between_sources_using_global_and_bilibili_intervals(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "runner-fetch-intervals.db")
    executed_names: list[str] = []
    sleep_calls: list[float] = []
    with session_factory() as session:
        session.add(
            Source(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                name="普通来源",
                site_name="Example",
                entry_url="https://example.com/a",
                fetch_mode="http",
                parser_type="generic_css",
                max_items=30,
                enabled=True,
            )
        )
        session.add(
            Source(
                id=UUID("00000000-0000-0000-0000-000000000002"),
                name="B站来源",
                site_name="Bilibili",
                entry_url="https://www.bilibili.com/",
                fetch_mode="http",
                parser_type="generic_css",
                max_items=30,
                enabled=True,
            )
        )
        session.add(
            Source(
                id=UUID("00000000-0000-0000-0000-000000000003"),
                name="第二个普通来源",
                site_name="Example",
                entry_url="https://example.com/b",
                fetch_mode="http",
                parser_type="generic_css",
                max_items=30,
                enabled=True,
            )
        )
        session.commit()
        JobService(session).create_manual_job()

    def record_executor(source: Source) -> dict[str, object]:
        executed_names.append(source.name)
        return {"item_count": 1, "items": []}

    runner = JobRunner(
        session_factory=session_factory,
        source_executor=record_executor,
        notification_scheduler=lambda task: task(),
        settings_provider=lambda: SimpleNamespace(
            source_fetch_interval_seconds=3,
            bilibili_source_interval_seconds=12,
        ),
        sleeper=lambda seconds: sleep_calls.append(seconds),
    )

    runner.run_once()

    assert executed_names == ["普通来源", "B站来源", "第二个普通来源"]
    assert sleep_calls == [15.0, 3.0]


def test_runner_logs_warning_when_dingtalk_notification_is_skipped_for_no_new_items(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "runner-dingtalk-no-new-items.db")
    monkeypatch.setenv("ENABLE_DINGTALK_NOTIFIER", "true")
    monkeypatch.setenv("DINGTALK_WEBHOOK", "https://oapi.dingtalk.com/robot/send?access_token=test-token")
    with session_factory() as session:
        session.add(
            Source(
                name="NGA",
                site_name="NGA",
                entry_url="https://example.com",
                fetch_mode="http",
                parser_type="generic_css",
                max_items=30,
                enabled=True,
            )
        )
        session.commit()
        JobService(session).create_manual_job()
        JobService(session).create_manual_job()

    sent_payloads: list[object] = []

    def fake_send(self, webhook: str, payload: dict[str, object], timeout_seconds: float, secret: str | None) -> None:
        sent_payloads.append(payload)

    monkeypatch.setattr(DingTalkWebhookService, "_send_webhook", fake_send)

    runner = JobRunner(
        session_factory=session_factory,
        source_executor=lambda source: {
            "item_count": 1,
            "items": [
                {
                    "title": "持续命中帖子",
                    "url": "https://example.com/post-keep",
                    "published_at": "2026-03-24 09:00",
                }
            ],
        },
        notification_scheduler=lambda task: task(),
    )

    first_processed_job_id = runner.run_once()
    second_processed_job_id = runner.run_once()

    with session_factory() as session:
        job = session.get(CollectionJob, second_processed_job_id)
        logs = list(session.scalars(select(JobLog).where(JobLog.job_id == second_processed_job_id).order_by(JobLog.created_at.asc())).all())

        assert first_processed_job_id is not None
        assert second_processed_job_id is not None
        assert job is not None
        assert job.status == "success"
        assert len(sent_payloads) == 1
        assert any(
            log.level == "warning"
            and "dingtalk notification skipped: no new collected items in current job" in log.message
            for log in logs
        )


def test_runner_uses_report_root_captured_at_construction(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "runner-report-root-freeze.db")
    original_reports_root = tmp_path / "reports"
    with session_factory() as session:
        session.add(
            Source(
                name="NGA",
                site_name="NGA",
                entry_url="https://example.com",
                fetch_mode="http",
                parser_type="generic_css",
                max_items=30,
                enabled=True,
            )
        )
        session.commit()
        JobService(session).create_manual_job()

    runner = JobRunner(
        session_factory=session_factory,
        source_executor=lambda source: {
            "item_count": 1,
            "items": [
                {
                    "title": "固定报告目录",
                    "url": "https://example.com/post-1",
                    "published_at": "2026-03-24 08:00",
                }
            ],
        },
        notification_scheduler=lambda task: task(),
    )

    monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "changed-reports"))

    runner.run_once()

    assert (original_reports_root / "global" / "hot-report.md").exists()
    assert not (tmp_path / "changed-reports" / "global" / "hot-report.md").exists()



