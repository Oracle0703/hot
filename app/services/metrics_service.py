"""阶段 3.2 — 任务指标聚合服务(REQ-OPS-003)。

提供 ``compute_job_metrics(session, since=None)`` 给 ``GET /system/metrics``。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import CollectionJob


@dataclass(slots=True)
class JobMetrics:
    window_hours: float
    total_jobs: int
    success_jobs: int
    failed_jobs: int
    cancelled_jobs: int
    success_rate: float
    p50_duration_seconds: float | None
    p95_duration_seconds: float | None
    avg_duration_seconds: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "window_hours": self.window_hours,
            "total_jobs": self.total_jobs,
            "success_jobs": self.success_jobs,
            "failed_jobs": self.failed_jobs,
            "cancelled_jobs": self.cancelled_jobs,
            "success_rate": round(self.success_rate, 4),
            "p50_duration_seconds": self.p50_duration_seconds,
            "p95_duration_seconds": self.p95_duration_seconds,
            "avg_duration_seconds": self.avg_duration_seconds,
        }


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return round(sorted_values[0], 3)
    # 线性插值
    k = (len(sorted_values) - 1) * pct
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return round(sorted_values[f], 3)
    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return round(d0 + d1, 3)


def compute_job_metrics(session: Session, *, since: Optional[datetime] = None,
                        window_hours: float = 24.0) -> JobMetrics:
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    stmt = select(
        CollectionJob.id,
        CollectionJob.status,
        CollectionJob.started_at,
        CollectionJob.finished_at,
    ).where(CollectionJob.started_at != None).where(CollectionJob.started_at >= since)  # noqa: E711
    rows = session.execute(stmt).all()

    durations: list[float] = []
    success = failed = cancelled = 0
    for _, status, started_at, finished_at in rows:
        if status == "success":
            success += 1
        elif status in ("failed", "partial_success"):
            failed += 1
        elif status == "cancelled":
            cancelled += 1
        if started_at and finished_at:
            delta = (finished_at - started_at).total_seconds()
            if delta >= 0:
                durations.append(delta)

    total = len(rows)
    success_rate = (success / total) if total else 0.0
    avg_duration = round(sum(durations) / len(durations), 3) if durations else None

    return JobMetrics(
        window_hours=window_hours,
        total_jobs=total,
        success_jobs=success,
        failed_jobs=failed,
        cancelled_jobs=cancelled,
        success_rate=success_rate,
        p50_duration_seconds=_percentile(durations, 0.50),
        p95_duration_seconds=_percentile(durations, 0.95),
        avg_duration_seconds=avg_duration,
    )


__all__ = ["compute_job_metrics", "JobMetrics"]
