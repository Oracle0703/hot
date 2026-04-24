from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CollectedItem(Base):
    __tablename__ = "collected_items"
    __table_args__ = (UniqueConstraint("normalized_hash"),)

    id: Mapped[str] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[str] = mapped_column(Uuid, ForeignKey("sources.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(Uuid, ForeignKey("collection_jobs.id"), nullable=False)
    first_seen_job_id: Mapped[str | None] = mapped_column(Uuid, ForeignKey("collection_jobs.id"), nullable=True)
    last_seen_job_id: Mapped[str | None] = mapped_column(Uuid, ForeignKey("collection_jobs.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heat_score: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    like_count: Mapped[int | None] = mapped_column(nullable=True)
    reply_count: Mapped[int | None] = mapped_column(nullable=True)
    view_count: Mapped[int | None] = mapped_column(nullable=True)
    recommended_grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    manual_grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    pushed_to_dingtalk_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pushed_to_dingtalk_batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_urls: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    normalized_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    source = relationship("Source", back_populates="items")
    job = relationship("CollectionJob", back_populates="items", foreign_keys=[job_id])

