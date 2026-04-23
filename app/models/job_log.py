from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class JobLog(Base):
    __tablename__ = "job_logs"

    id: Mapped[str] = mapped_column(Uuid, primary_key=True, default=uuid4)
    job_id: Mapped[str] = mapped_column(Uuid, ForeignKey("collection_jobs.id"), nullable=False)
    source_id: Mapped[str | None] = mapped_column(Uuid, ForeignKey("sources.id"), nullable=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    job = relationship("CollectionJob", back_populates="logs")
