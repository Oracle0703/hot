from __future__ import annotations

import re
from datetime import datetime

_DATE_ONLY_PATTERN = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$")
_ENGLISH_DATE_ONLY_PATTERN = re.compile(
    r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|January|February|March|April|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}$",
    re.IGNORECASE,
)
_EXPLICIT_TIME_PATTERN = re.compile(r"(?:^|[T\s])\d{1,2}:\d{2}(?::\d{2})?(?:$|[Z+\-])")


def format_published_at(value: datetime | None, raw_text: object) -> str:
    normalized_text = _normalize_text(raw_text)
    if normalized_text is not None:
        parsed_text = _parse_published_at_text(normalized_text)
        if parsed_text is None:
            return normalized_text
        if _looks_like_date_only_text(normalized_text):
            return parsed_text.strftime("%Y-%m-%d")
        if _looks_like_explicit_time_text(normalized_text):
            return parsed_text.strftime("%Y-%m-%d %H:%M")
        return normalized_text

    if value is None:
        return "未知时间"
    if _has_zero_clock_time(value):
        return value.strftime("%Y-%m-%d")
    return value.strftime("%Y-%m-%d %H:%M")


def _parse_published_at_text(text: str) -> datetime | None:
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _looks_like_date_only_text(text: str) -> bool:
    return _DATE_ONLY_PATTERN.fullmatch(text) is not None or _ENGLISH_DATE_ONLY_PATTERN.fullmatch(text) is not None


def _looks_like_explicit_time_text(text: str) -> bool:
    return _EXPLICIT_TIME_PATTERN.search(text) is not None


def _has_zero_clock_time(value: datetime) -> bool:
    return (
        value.hour == 0
        and value.minute == 0
        and value.second == 0
        and value.microsecond == 0
    )
