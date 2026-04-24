from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.item import CollectedItem

GRADE_OPTIONS = ("S", "A+", "A", "B+", "B", "C", "D")
_GRADE_ORDER = {grade: index for index, grade in enumerate(GRADE_OPTIONS)}


class WeeklyRatingService:
    def __init__(self, session: Session | None = None) -> None:
        self.session = session

    def recommend_grade(self, item) -> str:
        score = self._score_views(getattr(item, "view_count", None))
        score += self._score_likes(getattr(item, "like_count", None))
        score += self._score_replies(getattr(item, "reply_count", None))
        if score >= 11:
            return "S"
        if score >= 8:
            return "A+"
        if score >= 6:
            return "A"
        if score >= 4:
            return "B+"
        if score >= 3:
            return "B"
        if score >= 1:
            return "C"
        return "D"

    def is_grade_at_least(self, current_grade: str | None, threshold_grade: str | None) -> bool:
        normalized_current = self.normalize_grade(current_grade)
        normalized_threshold = self.normalize_grade(threshold_grade) or "B+"
        if normalized_current is None:
            return False
        return _GRADE_ORDER[normalized_current] <= _GRADE_ORDER[normalized_threshold]

    def normalize_grade(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().upper()
        return normalized if normalized in _GRADE_ORDER else None

    def refresh_recommended_grades(self, items: list[CollectedItem]) -> None:
        if self.session is None:
            return
        changed = self.assign_recommended_grades(items)
        if changed:
            self.session.commit()

    def assign_recommended_grades(self, items: list[CollectedItem]) -> bool:
        changed = False
        for item in items:
            recommended = self.recommend_grade(item)
            if getattr(item, "recommended_grade", None) != recommended:
                item.recommended_grade = recommended
                changed = True
        return changed

    def save_manual_grades(self, grades_by_item_id: dict[str, str | None]) -> int:
        if self.session is None or not grades_by_item_id:
            return 0

        updated = 0
        for raw_item_id, raw_grade in grades_by_item_id.items():
            try:
                item_uuid = UUID(str(raw_item_id))
            except ValueError:
                continue
            item = self.session.scalar(select(CollectedItem).where(CollectedItem.id == item_uuid))
            if item is None:
                continue
            normalized_grade = self.normalize_grade(raw_grade)
            if item.manual_grade != normalized_grade:
                item.manual_grade = normalized_grade
                updated += 1
        if updated:
            self.session.commit()
        return updated

    def _score_views(self, value: int | None) -> int:
        number = int(value or 0)
        if number >= 100000:
            return 6
        if number >= 50000:
            return 5
        if number >= 20000:
            return 4
        if number >= 10000:
            return 3
        if number >= 3000:
            return 2
        if number >= 1000:
            return 1
        return 0

    def _score_likes(self, value: int | None) -> int:
        number = int(value or 0)
        if number >= 5000:
            return 4
        if number >= 2000:
            return 3
        if number >= 800:
            return 2
        if number >= 200:
            return 1
        return 0

    def _score_replies(self, value: int | None) -> int:
        number = int(value or 0)
        if number >= 500:
            return 3
        if number >= 200:
            return 2
        if number >= 50:
            return 1
        return 0
