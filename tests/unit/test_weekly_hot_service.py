from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.item import CollectedItem
from app.models.source import Source
from app.services.weekly_hot_service import WeeklyHotService


def setup_database(tmp_path: Path, name: str):
    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / name).as_posix()}"
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory()


def create_source(session, name: str) -> Source:
    source = Source(
        name=name,
        site_name=name,
        entry_url=f"https://example.com/{name}",
        fetch_mode="http",
        parser_type="generic_css",
        max_items=10,
        enabled=True,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def as_uuid(value: str) -> UUID:
    return UUID(value)


def test_weekly_hot_service_filters_last_7_days_and_sorts_by_published_at_desc(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "weekly-hot-service.db")
    now = datetime(2026, 4, 23, 20, 0, 0)

    with session_factory() as session:
        source = create_source(session, "bilibili")
        session.add_all(
            [
                CollectedItem(
                    source_id=source.id,
                    job_id=as_uuid("11111111-1111-1111-1111-111111111111"),
                    first_seen_job_id=as_uuid("11111111-1111-1111-1111-111111111111"),
                    last_seen_job_id=as_uuid("11111111-1111-1111-1111-111111111111"),
                    title="最近发布的视频",
                    url="https://example.com/video-1",
                    published_at=now - timedelta(hours=1),
                    published_at_text="2026-04-23 19:00:00",
                    first_seen_at=now - timedelta(days=1),
                    last_seen_at=now - timedelta(days=1),
                    normalized_hash="hash-1",
                ),
                CollectedItem(
                    source_id=source.id,
                    job_id=as_uuid("22222222-2222-2222-2222-222222222222"),
                    first_seen_job_id=as_uuid("22222222-2222-2222-2222-222222222222"),
                    last_seen_job_id=as_uuid("22222222-2222-2222-2222-222222222222"),
                    title="上周的视频",
                    url="https://example.com/video-2",
                    published_at=now - timedelta(days=2),
                    published_at_text="2026-04-21 10:00:00",
                    first_seen_at=now - timedelta(days=2),
                    last_seen_at=now - timedelta(days=2),
                    normalized_hash="hash-2",
                ),
                CollectedItem(
                    source_id=source.id,
                    job_id=as_uuid("33333333-3333-3333-3333-333333333333"),
                    first_seen_job_id=as_uuid("33333333-3333-3333-3333-333333333333"),
                    last_seen_job_id=as_uuid("33333333-3333-3333-3333-333333333333"),
                    title="超过一周的视频",
                    url="https://example.com/video-3",
                    published_at=now - timedelta(days=8),
                    published_at_text="2026-04-15 09:00:00",
                    first_seen_at=now - timedelta(days=8),
                    last_seen_at=now - timedelta(days=8),
                    normalized_hash="hash-3",
                ),
            ]
        )
        session.commit()

        items = WeeklyHotService(session).list_recent_items(now=now)

    assert [item.title for item in items] == ["最近发布的视频", "上周的视频"]


def test_weekly_hot_service_falls_back_to_first_seen_at_when_published_at_missing(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "weekly-hot-service-fallback.db")
    now = datetime(2026, 4, 23, 20, 0, 0)

    with session_factory() as session:
        source = create_source(session, "fallback")
        session.add_all(
            [
                CollectedItem(
                    source_id=source.id,
                    job_id=as_uuid("44444444-4444-4444-4444-444444444444"),
                    first_seen_job_id=as_uuid("44444444-4444-4444-4444-444444444444"),
                    last_seen_job_id=as_uuid("44444444-4444-4444-4444-444444444444"),
                    title="较新的采集",
                    url="https://example.com/video-4",
                    first_seen_at=now - timedelta(hours=2),
                    last_seen_at=now - timedelta(hours=2),
                    normalized_hash="hash-4",
                ),
                CollectedItem(
                    source_id=source.id,
                    job_id=as_uuid("55555555-5555-5555-5555-555555555555"),
                    first_seen_job_id=as_uuid("55555555-5555-5555-5555-555555555555"),
                    last_seen_job_id=as_uuid("55555555-5555-5555-5555-555555555555"),
                    title="较早的采集",
                    url="https://example.com/video-5",
                    first_seen_at=now - timedelta(days=1),
                    last_seen_at=now - timedelta(days=1),
                    normalized_hash="hash-5",
                ),
            ]
        )
        session.commit()

        items = WeeklyHotService(session).list_recent_items(now=now)

    assert [item.title for item in items] == ["较新的采集", "较早的采集"]
