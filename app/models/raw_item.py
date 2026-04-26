from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RawItem(Base):
    __tablename__ = "raw_items"

    id: Mapped[str] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[str] = mapped_column(Uuid, ForeignKey("sources.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(Uuid, ForeignKey("collection_jobs.id"), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
