from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(Uuid, primary_key=True, default=uuid4)
    job_id: Mapped[str] = mapped_column(Uuid, ForeignKey("collection_jobs.id"), nullable=False)
    markdown_path: Mapped[str] = mapped_column(Text, nullable=False)
    docx_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    job = relationship("CollectionJob", back_populates="reports")
