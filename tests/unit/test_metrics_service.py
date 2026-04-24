"""阶段 3.2 / REQ-OPS-003 — 任务指标聚合服务测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.base import Base
from app.models.job import CollectionJob
from app.services.metrics_service import compute_job_metrics
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/m.db", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    yield s
    s.close()


def _make_job(s, status: str, started_offset_h: float, duration_s: float):
    now = datetime.now(timezone.utc)
    started_at = now - timedelta(hours=started_offset_h)
    finished_at = started_at + timedelta(seconds=duration_s)
    job = CollectionJob(status=status, started_at=started_at, finished_at=finished_at,
                       total_sources=1, completed_sources=1)
    s.add(job)
    s.commit()
    return job


def test_metrics_empty_returns_zero(session) -> None:
    m = compute_job_metrics(session, window_hours=24)
    assert m.total_jobs == 0
    assert m.success_rate == 0.0
    assert m.p50_duration_seconds is None


def test_metrics_success_rate_and_percentiles(session) -> None:
    _make_job(session, "success", 1, 10)
    _make_job(session, "success", 2, 20)
    _make_job(session, "success", 3, 30)
    _make_job(session, "failed", 4, 40)
    m = compute_job_metrics(session, window_hours=24)
    assert m.total_jobs == 4
    assert m.success_jobs == 3
    assert m.failed_jobs == 1
    assert m.success_rate == 0.75
    assert m.p50_duration_seconds == 25.0  # 中位
    assert m.p95_duration_seconds is not None
    assert m.avg_duration_seconds == 25.0


def test_metrics_excludes_jobs_outside_window(session) -> None:
    _make_job(session, "success", 30, 5)  # 30h ago, outside 24h window
    _make_job(session, "success", 1, 5)
    m = compute_job_metrics(session, window_hours=24)
    assert m.total_jobs == 1
