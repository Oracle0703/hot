"""TC-DISP-101~104 — JobRunner / cancel_registry 协作式取消。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.job import CollectionJob
from app.models.job_log import JobLog
from app.models.source import Source
from app.services import cancel_registry
from app.services.job_service import JobService
from app.workers.runner import JobRunner


def _make_db_url(tmp_path: Path, name: str = "cancel.db") -> str:
    return f"sqlite:///{(tmp_path / name).as_posix()}"


@pytest.fixture(autouse=True)
def _reset_cancel_registry():
    cancel_registry.clear()
    yield
    cancel_registry.clear()


def _bootstrap(tmp_path: Path, monkeypatch, source_count: int = 3):
    monkeypatch.setenv("DATABASE_URL", _make_db_url(tmp_path))
    monkeypatch.setenv("HOT_RUNTIME_ROOT", str(tmp_path))
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    factory = create_session_factory()
    with factory() as session:
        for i in range(source_count):
            session.add(
                Source(
                    name=f"src-{i}",
                    site_name="local",
                    entry_url=f"https://example.com/{i}",
                    fetch_mode="http",
                    parser_type="generic_css",
                    enabled=True,
                    max_items=10,
                )
            )
        session.commit()
        JobService(session).create_manual_job()
    return factory


def test_cooperative_cancel_marks_job_after_first_source(tmp_path, monkeypatch) -> None:
    """TC-DISP-101: 协作式取消,在第一个 source 完成后跳出剩余 source,任务变 cancelled"""
    factory = _bootstrap(tmp_path, monkeypatch, source_count=3)
    executed: list[str] = []

    def fake_executor(source: Source) -> dict[str, object]:
        executed.append(source.name)
        # 第一条执行完后立即触发取消
        if len(executed) == 1:
            with factory() as s:
                job = s.scalar(select(CollectionJob))
                cancel_registry.request_cancel(job.id)
        return {"item_count": 0, "items": []}

    runner = JobRunner(session_factory=factory, source_executor=fake_executor)
    runner.run_once()

    with factory() as session:
        job = session.scalar(select(CollectionJob))
        assert job.status == "cancelled"
        # 第一个 source 完成后即检查到 cancel,因此只跑了 1 个
        assert len(executed) == 1
        warn_logs = list(session.scalars(select(JobLog).where(JobLog.level == "warning")).all())
        assert any("cancelled" in (log.message or "") for log in warn_logs)


def test_cancel_when_no_running_returns_reason() -> None:
    """TC-DISP-103: cancel_registry.is_cancelled 对未登记任务返回 False"""
    from uuid import uuid4

    assert cancel_registry.is_cancelled(uuid4()) is False


def test_consume_returns_true_only_once() -> None:
    """TC-DISP-104: consume 第一次 True 之后变 False"""
    from uuid import uuid4

    job_id = uuid4()
    cancel_registry.request_cancel(job_id)
    assert cancel_registry.consume(job_id) is True
    assert cancel_registry.consume(job_id) is False


def test_force_cancel_interrupts_inflight_calls() -> None:
    """TC-DISP-102: force=true 后 is_force_cancelled 立即返回 True,
    模拟正在 inflight 的可取消任务可据此中断。"""
    from uuid import uuid4

    cancel_registry.clear()
    job_id = uuid4()
    cancel_registry.request_cancel(job_id, force=True)
    assert cancel_registry.is_cancelled(job_id) is True
    assert cancel_registry.is_force_cancelled(job_id) is True
    # consume 后两个标志一起清掉
    assert cancel_registry.consume(job_id) is True
    assert cancel_registry.is_cancelled(job_id) is False
    assert cancel_registry.is_force_cancelled(job_id) is False
