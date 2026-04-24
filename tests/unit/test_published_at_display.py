from __future__ import annotations

from datetime import datetime

from app.services.published_at_display import format_published_at


def test_format_published_at_keeps_seconds_when_raw_text_contains_explicit_seconds() -> None:
    value = datetime(2026, 4, 23, 19, 0, 0)

    assert format_published_at(value, "2026-04-23 19:00:00") == "2026-04-23 19:00:00"
