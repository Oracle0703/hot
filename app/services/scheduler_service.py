from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schedule_plan import SchedulePlan
from app.models.scheduler_setting import SchedulerSetting
from app.services.job_service import JobService
from app.services.schedule_plan_service import SchedulePlanService


class SchedulerService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.plan_service = SchedulePlanService(session)

    def get_settings(self) -> SchedulerSetting:
        settings = self.session.get(SchedulerSetting, 1)
        if settings is None:
            settings = SchedulerSetting(id=1, enabled=False, daily_time="08:00")
            self.session.add(settings)
            self.session.commit()
            self.session.refresh(settings)
        if self._ensure_legacy_default_plan(settings):
            self.session.commit()
        return settings

    def update_settings(self, enabled: bool, daily_time: str) -> SchedulerSetting:
        settings = self.get_settings()
        settings.enabled = enabled
        settings.daily_time = daily_time
        self._ensure_legacy_default_plan(settings, sync_existing_default_plan=True)
        self.session.commit()
        self.session.refresh(settings)
        return settings

    def run_due_jobs(self, now: datetime) -> list[object]:
        settings = self.get_settings()
        if not settings.enabled:
            return []

        created_jobs = []
        for plan in self.plan_service.list_due_plans(now):
            created_job = JobService(self.session).create_scheduled_job_for_plan(plan)
            if created_job is None:
                continue
            plan.last_triggered_on = now.date()
            created_jobs.append(created_job)

        if created_jobs:
            self.session.commit()
        return created_jobs

    def _ensure_legacy_default_plan(
        self,
        settings: SchedulerSetting,
        *,
        sync_existing_default_plan: bool = False,
    ) -> bool:
        if not settings.enabled or not settings.daily_time:
            return False

        plans = list(self.session.scalars(select(SchedulePlan).order_by(SchedulePlan.id.asc())).all())
        if not plans:
            self.session.add(
                SchedulePlan(
                    enabled=True,
                    run_time=settings.daily_time,
                    schedule_group="default",
                )
            )
            return True

        if not sync_existing_default_plan or len(plans) != 1:
            return False

        only_plan = plans[0]
        if only_plan.schedule_group == "default" and only_plan.run_time != settings.daily_time:
            only_plan.run_time = settings.daily_time
            return True
        return False
