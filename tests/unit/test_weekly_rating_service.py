from __future__ import annotations

from types import SimpleNamespace

from app.services.weekly_rating_service import WeeklyRatingService


def test_weekly_rating_service_recommends_grade_from_metrics() -> None:
    service = WeeklyRatingService()

    high_item = SimpleNamespace(view_count=120000, like_count=8000, reply_count=900)
    medium_item = SimpleNamespace(view_count=15000, like_count=600, reply_count=80)
    low_item = SimpleNamespace(view_count=300, like_count=10, reply_count=2)

    assert service.recommend_grade(high_item) == "S"
    assert service.recommend_grade(medium_item) == "B+"
    assert service.recommend_grade(low_item) == "D"


def test_weekly_rating_service_compares_grades_by_rank() -> None:
    service = WeeklyRatingService()

    assert service.is_grade_at_least("A", "B+") is True
    assert service.is_grade_at_least("B+", "B+") is True
    assert service.is_grade_at_least("B", "B+") is False
    assert service.is_grade_at_least(None, "B+") is False


def test_weekly_rating_service_normalizes_grade_text() -> None:
    service = WeeklyRatingService()

    assert service.normalize_grade(" a+ ") == "A+"
    assert service.normalize_grade("b+") == "B+"
    assert service.normalize_grade("unknown") is None
