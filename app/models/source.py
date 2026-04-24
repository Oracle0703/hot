from __future__ import annotations

from uuid import uuid4

from sqlalchemy import JSON, Boolean, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    site_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entry_url: Mapped[str] = mapped_column(Text, nullable=False)
    fetch_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    parser_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    list_selector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title_selector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    link_selector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta_selector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    include_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    exclude_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    max_items: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_group: Mapped[str | None] = mapped_column(String(20), nullable=True)
    schedule_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    collection_strategy: Mapped[str] = mapped_column(String(50), nullable=False, default="generic_css")
    search_keyword: Mapped[str | None] = mapped_column(String(200), nullable=True)
    retry_policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    items = relationship("CollectedItem", back_populates="source")
