from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.item import CollectedItem
from app.models.source import Source
from app.services.weekly_cover_cache_service import WeeklyCoverCacheService


def setup_database(tmp_path: Path, name: str):
    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / name).as_posix()}"
    os.environ["HOT_RUNTIME_ROOT"] = str(tmp_path)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory()


def create_source(session) -> Source:
    source = Source(
        name="source",
        site_name="source",
        entry_url="https://example.com/source",
        fetch_mode="http",
        parser_type="generic_css",
        max_items=10,
        enabled=True,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def create_item(session, source: Source, *, cover_url: str) -> CollectedItem:
    item = CollectedItem(
        source_id=source.id,
        job_id=UUID("99999999-9999-9999-9999-999999999999"),
        first_seen_job_id=UUID("99999999-9999-9999-9999-999999999999"),
        last_seen_job_id=UUID("99999999-9999-9999-9999-999999999999"),
        title="demo",
        url="https://example.com/post",
        first_seen_at=datetime(2026, 4, 23, 10, 0, 0),
        last_seen_at=datetime(2026, 4, 23, 10, 0, 0),
        cover_image_url=cover_url,
        normalized_hash="weekly-cover-cache-hash",
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def test_weekly_cover_cache_service_downloads_and_reuses_local_file(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "weekly-cover-cache.db")

    with session_factory() as session:
        source = create_source(session)
        item = create_item(session, source, cover_url="https://i0.hdslb.com/demo.jpg")
        service = WeeklyCoverCacheService(session)
        calls: list[str] = []

        def fake_download(self, image_url: str, destination_path: Path) -> Path | None:
            calls.append(image_url)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            destination_path.write_bytes(b"demo-image")
            return destination_path

        monkeypatch.setattr(WeeklyCoverCacheService, "_download_image", fake_download)

        first_path = service.get_cached_path(item)
        second_path = service.get_cached_path(item)

    assert first_path is not None
    assert second_path is not None
    assert first_path == second_path
    assert first_path.exists()
    assert calls == ["https://i0.hdslb.com/demo.jpg"]


def test_weekly_cover_cache_service_prunes_only_files_older_than_retention(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "weekly-cover-cache-prune.db")

    with session_factory() as session:
        source = create_source(session)
        item = create_item(session, source, cover_url="https://i0.hdslb.com/demo.jpg")
        service = WeeklyCoverCacheService(session)
        cache_dir = Path(tmp_path) / "outputs" / "weekly-covers"
        cache_dir.mkdir(parents=True, exist_ok=True)
        active_file = cache_dir / f"{item.id}-active.jpg"
        stale_file = cache_dir / f"{item.id}-stale.jpg"
        active_file.write_bytes(b"active")
        stale_file.write_bytes(b"stale")
        old_timestamp = (datetime(2026, 4, 1, 10, 0, 0)).timestamp()
        os.utime(stale_file, (old_timestamp, old_timestamp))

        service.prune(now=datetime(2026, 4, 23, 20, 0, 0), max_age_days=10)

    assert active_file.exists()
    assert not stale_file.exists()
