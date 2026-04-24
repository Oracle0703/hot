from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.item import CollectedItem


class WeeklyHotService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_recent_items(
        self,
        *,
        now: datetime | None = None,
        days: int = 7,
        limit: int = 500,
    ) -> list[CollectedItem]:
        current_time = now or datetime.utcnow()
        cutoff = current_time - timedelta(days=days)
        items = list(
            self.session.scalars(
                select(CollectedItem).where(
                    CollectedItem.first_seen_at.is_not(None),
                    CollectedItem.first_seen_at >= cutoff,
                )
            ).all()
        )
        items.sort(key=self._sort_key, reverse=True)
        return items[:limit]

    def _sort_key(self, item: CollectedItem) -> tuple[datetime, datetime]:
        published_or_seen_at = item.published_at or item.first_seen_at or datetime.min
        first_seen_at = item.first_seen_at or datetime.min
        return (published_or_seen_at, first_seen_at)
