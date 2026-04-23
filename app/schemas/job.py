from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trigger_type: str
    status: str
    total_sources: int
    completed_sources: int
    success_sources: int
    failed_sources: int
    current_source: str | None
    started_at: datetime | None
    finished_at: datetime | None
    report_id: UUID | None = None


class JobLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    source_id: UUID | None
    level: str
    message: str
    created_at: datetime
