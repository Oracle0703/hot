from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.scheduler_setting import SchedulerSetting
from app.services.job_service import JobService


class SchedulerService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_settings(self) -> SchedulerSetting:
        settings = self.session.get(SchedulerSetting, 1)
        if settings is None:
            settings = SchedulerSetting(id=1, enabled=False, daily_time="08:00")
            self.session.add(settings)
            self.session.commit()
            self.session.refresh(settings)
        return settings

    def update_settings(self, enabled: bool, daily_time: str) -> SchedulerSetting:
        settings = self.get_settings()
        settings.enabled = enabled
        settings.daily_time = daily_time
        self.session.commit()
        self.session.refresh(settings)
        return settings

    def run_due_jobs(self, now: datetime) -> object | None:
        settings = self.get_settings()
        if not settings.enabled:
            return None
        if now.strftime("%H:%M") < settings.daily_time:
            return None
        if settings.last_triggered_on == now.date():
            return None

        created_job = JobService(self.session).create_scheduled_job()
        settings.last_triggered_on = now.date()
        self.session.commit()
        self.session.refresh(settings)
        return created_job
