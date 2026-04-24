from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schedule_plan import SchedulePlan


class SchedulePlanService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_plans(self) -> list[SchedulePlan]:
        statement = select(SchedulePlan).order_by(SchedulePlan.run_time.asc(), SchedulePlan.id.asc())
        return list(self.session.scalars(statement).all())

    def create_plan(self, *, enabled: bool, run_time: str, schedule_group: str) -> SchedulePlan:
        plan = SchedulePlan(enabled=enabled, run_time=run_time, schedule_group=schedule_group)
        self.session.add(plan)
        self.session.commit()
        self.session.refresh(plan)
        return plan

    def get_plan(self, plan_id: int) -> SchedulePlan | None:
        return self.session.get(SchedulePlan, plan_id)

    def update_plan(self, plan_id: int, *, enabled: bool, run_time: str, schedule_group: str) -> SchedulePlan | None:
        plan = self.get_plan(plan_id)
        if plan is None:
            return None
        plan.enabled = enabled
        plan.run_time = run_time
        plan.schedule_group = schedule_group
        self.session.commit()
        self.session.refresh(plan)
        return plan

    def delete_plan(self, plan_id: int) -> bool:
        plan = self.get_plan(plan_id)
        if plan is None:
            return False
        self.session.delete(plan)
        self.session.commit()
        return True

    def list_due_plans(self, now: datetime) -> list[SchedulePlan]:
        current_time = now.strftime("%H:%M")
        statement = (
            select(SchedulePlan)
            .where(SchedulePlan.enabled.is_(True))
            .where(SchedulePlan.run_time <= current_time)
            .where(
                (SchedulePlan.last_triggered_on.is_(None))
                | (SchedulePlan.last_triggered_on != now.date())
            )
            .order_by(SchedulePlan.run_time.asc(), SchedulePlan.id.asc())
        )
        return list(self.session.scalars(statement).all())
