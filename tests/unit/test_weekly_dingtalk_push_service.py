from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from app.config import Settings
from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.item import CollectedItem
from app.models.source import Source
from app.services.weekly_dingtalk_push_service import WeeklyDingTalkPushService


def setup_database(tmp_path: Path, name: str):
    os.environ["HOT_RUNTIME_ROOT"] = str(tmp_path)
    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / name).as_posix()}"
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory()


def create_source(session) -> Source:
    source = Source(
        name="测试来源",
        site_name="Bilibili",
        entry_url="https://space.bilibili.com/281232336",
        fetch_mode="http",
        parser_type="generic_css",
        max_items=10,
        enabled=True,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def create_item(
    session,
    source: Source,
    *,
    suffix: str,
    manual_grade: str | None,
    recommended_grade: str,
    pushed: bool = False,
) -> CollectedItem:
    item = CollectedItem(
        source_id=source.id,
        job_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        first_seen_job_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        last_seen_job_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        title=f"视频{suffix}",
        url=f"https://www.bilibili.com/video/BV{suffix}",
        author="测试UP",
        published_at=datetime(2026, 4, 23, 19, 0, 0),
        published_at_text="2026-04-23 19:00:00",
        first_seen_at=datetime(2026, 4, 23, 20, 0, 0),
        last_seen_at=datetime(2026, 4, 23, 20, 0, 0),
        like_count=137,
        reply_count=53,
        view_count=3356,
        recommended_grade=recommended_grade,
        manual_grade=manual_grade,
        pushed_to_dingtalk_at=datetime(2026, 4, 23, 21, 0, 0) if pushed else None,
        pushed_to_dingtalk_batch_id="batch-old" if pushed else None,
        normalized_hash=f"weekly-push-{suffix}",
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def test_weekly_dingtalk_push_service_pushes_only_eligible_unpushed_items(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "weekly-dingtalk-push.db")

    with session_factory() as session:
        source = create_source(session)
        eligible = create_item(session, source, suffix="111", manual_grade="A", recommended_grade="B+")
        create_item(session, source, suffix="222", manual_grade="B", recommended_grade="A")
        create_item(session, source, suffix="333", manual_grade="S", recommended_grade="S", pushed=True)
        requests: list[dict[str, object]] = []

        def fake_sender(webhook: str, payload: dict[str, object], timeout_seconds: float, secret: str | None) -> None:
            requests.append({"webhook": webhook, "payload": payload, "secret": secret})

        service = WeeklyDingTalkPushService(
            session,
            settings=Settings(
                enable_dingtalk_notifier=True,
                dingtalk_webhook="https://oapi.dingtalk.com/robot/send?access_token=test-token",
                weekly_grade_push_threshold="B+",
            ),
            sender=fake_sender,
        )

        pushed_count = service.push_items([eligible.id])
        session.refresh(eligible)

    assert pushed_count == 1
    assert len(requests) == 1
    markdown = requests[0]["payload"]["markdown"]
    assert markdown["title"] == "热点报告 筛选结果"
    assert "[视频111](https://www.bilibili.com/video/BV111)" in markdown["text"]
    assert "评分：A" in markdown["text"]
    assert "推荐评分" not in markdown["text"]
    assert "人工评分" not in markdown["text"]
    assert eligible.pushed_to_dingtalk_at is not None
    assert eligible.pushed_to_dingtalk_batch_id
    parsed = urlparse(requests[0]["webhook"])
    assert parse_qs(parsed.query)["access_token"] == ["test-token"]


def test_weekly_dingtalk_push_service_returns_zero_when_no_items_match_threshold(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "weekly-dingtalk-push-empty.db")

    with session_factory() as session:
        source = create_source(session)
        item = create_item(session, source, suffix="444", manual_grade="B", recommended_grade="A")
        service = WeeklyDingTalkPushService(
            session,
            settings=Settings(
                enable_dingtalk_notifier=True,
                dingtalk_webhook="https://oapi.dingtalk.com/robot/send?access_token=test-token",
                weekly_grade_push_threshold="B+",
            ),
            sender=lambda webhook, payload, timeout_seconds, secret: None,
        )

        pushed_count = service.push_items([item.id])

    assert pushed_count == 0
