from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes_sources import get_db_session
from app.models.job import CollectionJob
from app.schemas.job import JobLogRead, JobRead
from app.services.job_service import JobService

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def serialize_job(job: CollectionJob, report_id: str | None) -> dict[str, object]:
    return {
        "id": job.id,
        "trigger_type": job.trigger_type,
        "status": job.status,
        "total_sources": job.total_sources,
        "completed_sources": job.completed_sources,
        "success_sources": job.success_sources,
        "failed_sources": job.failed_sources,
        "current_source": job.current_source,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "report_id": report_id,
    }


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(session: Session = Depends(get_db_session)) -> dict[str, object]:
    service = JobService(session)
    job = service.create_manual_job()
    return serialize_job(job, report_id=None)


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, session: Session = Depends(get_db_session)) -> dict[str, object]:
    service = JobService(session)
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return serialize_job(job, report_id=service.get_report_id(job_id))


@router.get("/{job_id}/logs", response_model=list[JobLogRead])
def get_job_logs(job_id: str, session: Session = Depends(get_db_session)) -> list[JobLogRead]:
    service = JobService(session)
    if service.get_job(job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return [JobLogRead.model_validate(log) for log in service.list_job_logs(job_id)]
