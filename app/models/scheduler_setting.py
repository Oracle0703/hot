from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SchedulerSetting(Base):
    __tablename__ = "scheduler_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    daily_time: Mapped[str] = mapped_column(String(5), nullable=False, default="08:00")
    last_triggered_on: Mapped[date | None] = mapped_column(Date, nullable=True)
