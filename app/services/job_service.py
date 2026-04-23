from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.job import CollectionJob
from app.models.job_log import JobLog
from app.models.report import Report
from app.models.source import Source


class JobService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_manual_job(self) -> CollectionJob:
        total_sources = self.session.scalar(select(func.count()).select_from(Source).where(Source.enabled.is_(True)))
        job = CollectionJob(trigger_type="manual", status="pending", total_sources=total_sources or 0)
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def create_manual_job_for_group(self, group: str) -> CollectionJob | None:
        total_sources = self.session.scalar(
            select(func.count()).select_from(Source).where(Source.enabled.is_(True), Source.source_group == group)
        )
        if not total_sources:
            return None
        job = CollectionJob(
            trigger_type="manual",
            status="pending",
            source_group_scope=group,
            total_sources=total_sources or 0,
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def create_scheduled_job(self) -> CollectionJob:
        total_sources = self.session.scalar(select(func.count()).select_from(Source).where(Source.enabled.is_(True)))
        job = CollectionJob(trigger_type="scheduled", status="pending", total_sources=total_sources or 0)
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get_job(self, job_id: str) -> CollectionJob | None:
        return self.session.get(CollectionJob, UUID(job_id))

    def get_report_id(self, job_id: str) -> UUID | None:
        report = self.session.scalar(select(Report).order_by(Report.created_at.asc()).limit(1))
        return None if report is None else report.id

    def get_latest_error_message(self, job_id: str) -> str | None:
        statement = (
            select(JobLog.message)
            .where(JobLog.job_id == UUID(job_id), JobLog.level == "error")
            .order_by(JobLog.created_at.desc(), JobLog.id.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def list_job_logs(self, job_id: str) -> list[JobLog]:
        statement = select(JobLog).where(JobLog.job_id == UUID(job_id)).order_by(JobLog.created_at.asc())
        return list(self.session.scalars(statement).all())

    def list_recent_jobs(self, limit: int = 5) -> list[CollectionJob]:
        activity_at = func.coalesce(CollectionJob.finished_at, CollectionJob.started_at)
        statement = (
            select(CollectionJob)
            .order_by(activity_at.is_(None), activity_at.desc(), CollectionJob.id.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement).all())

