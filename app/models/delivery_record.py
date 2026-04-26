from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DeliveryRecord(Base):
    __tablename__ = "delivery_records"
    __table_args__ = (UniqueConstraint("subscription_id", "content_item_id"),)

    id: Mapped[str] = mapped_column(Uuid, primary_key=True, default=uuid4)
    subscription_id: Mapped[str] = mapped_column(Uuid, ForeignKey("subscriptions.id"), nullable=False)
    content_item_id: Mapped[str] = mapped_column(Uuid, ForeignKey("content_items.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="sent")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
