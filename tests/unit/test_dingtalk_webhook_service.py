from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.config import Settings
from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.job_log import JobLog
from app.models.source import Source
from app.services.dingtalk_webhook_service import DingTalkWebhookService
from app.services.job_service import JobService
from app.services.report_service import ReportService


def setup_database(tmp_path: Path, name: str):
    os.environ["HOT_RUNTIME_ROOT"] = str(tmp_path)
    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / name).as_posix()}"
    os.environ["REPORTS_ROOT"] = str(tmp_path / "reports")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory()


def create_source(session, name: str, entry_url: str) -> Source:
    source = Source(
        name=name,
        site_name=name,
        entry_url=entry_url,
        fetch_mode="http",
        parser_type="generic_css",
        list_selector=".topic",
        title_selector=".topic-link",
        link_selector=".topic-link",
        meta_selector=".topic-time",
        include_keywords=[],
        exclude_keywords=[],
        max_items=10,
        enabled=True,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def test_dingtalk_webhook_service_sends_one_message_per_source_with_throttle(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "dingtalk-webhook-summary.db")

    with session_factory() as session:
        source = create_source(session, "A频道", "https://example.com/source-a")
        second_source = create_source(session, "B频道", "https://example.com/source-b")
        failed_source = create_source(session, "失效来源", "https://example.com/source-b")
        first_job = JobService(session).create_manual_job()
        second_job = JobService(session).create_manual_job()
        report_service = ReportService(session)

        report_service.generate_for_job(
            first_job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "老帖子",
                            "url": "https://example.com/post-old",
                            "published_at": "2026-03-24 08:00",
                        },
                        {
                            "title": "持续命中帖子",
                            "url": "https://example.com/post-keep",
                            "published_at": "2026-03-24 09:00",
                        },
                    ],
                }
            ],
        )
        report_service.generate_for_job(
            second_job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "持续命中帖子",
                            "url": "https://example.com/post-keep",
                            "published_at": "2026-03-24 09:00",
                        },
                        {
                            "title": "A新帖子1",
                            "url": "https://example.com/post-a-new-1",
                            "published_at": "2026-03-24 10:00",
                        },
                        {
                            "title": "A新帖子2",
                            "url": "https://example.com/post-a-new-2",
                            "published_at": "2026-03-24 10:01",
                        },
                        {
                            "title": "A新帖子3",
                            "url": "https://example.com/post-a-new-3",
                            "published_at": "2026-03-24 10:02",
                        },
                        {
                            "title": "A新帖子4",
                            "url": "https://example.com/post-a-new-4",
                            "published_at": "2026-03-24 10:03",
                        },
                    ],
                },
                {
                    "source_id": second_source.id,
                    "source_name": second_source.name,
                    "items": [
                        {
                            "title": "B新帖子1",
                            "url": "https://example.com/post-b-new-1",
                            "published_at": "2026-03-24 11:00",
                        }
                    ],
                }
            ],
        )
        session.add(
            JobLog(
                job_id=second_job.id,
                source_id=failed_source.id,
                level="error",
                message="selector missing",
            )
        )
        session.commit()

        requests: list[dict[str, object]] = []
        sleep_calls: list[float] = []

        def fake_sender(
            webhook: str,
            payload: dict[str, object],
            timeout_seconds: float,
            secret: str | None,
        ) -> None:
            requests.append(
                {
                    "webhook": webhook,
                    "payload": payload,
                    "timeout_seconds": timeout_seconds,
                    "secret": secret,
                }
            )

        def fake_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        service = DingTalkWebhookService(
            session=session,
            settings=Settings(
                dingtalk_webhook="https://oapi.dingtalk.com/robot/send?access_token=test-token",
                dingtalk_secret="SECtest",
                dingtalk_keyword="热点报告",
                enable_dingtalk_notifier=True,
            ),
            sender=fake_sender,
            sleeper=fake_sleep,
        )

        assert service.notify_job_summary(second_job) is True
        assert len(requests) == 2
        assert sleep_calls == [3.0]

        first_markdown = requests[0]["payload"]["markdown"]
        second_markdown = requests[1]["payload"]["markdown"]

        assert first_markdown["title"] == "热点报告 A频道"
        assert "### 热点报告 A频道" in first_markdown["text"]
        assert "1. [A新帖子1](https://example.com/post-a-new-1)" in first_markdown["text"]
        assert "发布时间：2026-03-24 10:00" in first_markdown["text"]
        assert "2. [A新帖子2](https://example.com/post-a-new-2)" in first_markdown["text"]
        assert "发布时间：2026-03-24 10:01" in first_markdown["text"]
        assert "3. [A新帖子3](https://example.com/post-a-new-3)" in first_markdown["text"]
        assert "发布时间：2026-03-24 10:02" in first_markdown["text"]
        assert "4. [A新帖子4](https://example.com/post-a-new-4)" in first_markdown["text"]
        assert "发布时间：2026-03-24 10:03" in first_markdown["text"]

        assert second_markdown["title"] == "热点报告 B频道"
        assert "### 热点报告 B频道" in second_markdown["text"]
        assert "1. [B新帖子1](https://example.com/post-b-new-1)" in second_markdown["text"]
        assert "发布时间：2026-03-24 11:00" in second_markdown["text"]


def test_dingtalk_webhook_service_uses_bilibili_up_name_and_hides_job_id(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "dingtalk-webhook-bilibili-display-name.db")

    with session_factory() as session:
        source = create_source(session, "B站UP-20411266-视频投稿", "https://space.bilibili.com/20411266")
        source.collection_strategy = "bilibili_profile_videos_recent"
        job = JobService(session).create_manual_job()
        ReportService(session).generate_for_job(
            job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "UP主新投稿",
                            "url": "https://www.bilibili.com/video/BV1UP",
                            "author": "真实UP主",
                            "published_at": "2026-03-24",
                        }
                    ],
                }
            ],
        )

        requests: list[dict[str, object]] = []

        def fake_sender(
            webhook: str,
            payload: dict[str, object],
            timeout_seconds: float,
            secret: str | None,
        ) -> None:
            requests.append(payload)

        service = DingTalkWebhookService(
            session=session,
            settings=Settings(
                dingtalk_webhook="https://oapi.dingtalk.com/robot/send?access_token=test-token",
                dingtalk_keyword="热点报告",
                enable_dingtalk_notifier=True,
            ),
            sender=fake_sender,
        )

        assert service.notify_job_summary(job) is True
        assert len(requests) == 1

        markdown = requests[0]["markdown"]
        assert markdown["title"] == "热点报告 真实UP主"
        assert str(job.id) not in markdown["text"]
        assert "### 热点报告 真实UP主" in markdown["text"]
        assert "B站UP-20411266-视频投稿" not in markdown["text"]


def test_dingtalk_webhook_service_formats_bilibili_stats_on_second_line(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "dingtalk-webhook-bilibili-stats.db")

    with session_factory() as session:
        source = create_source(session, "B站UP-4186021-视频投稿", "https://space.bilibili.com/4186021")
        source.collection_strategy = "bilibili_profile_videos_recent"
        job = JobService(session).create_manual_job()
        ReportService(session).generate_for_job(
            job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "PRAGMATA/识质存在：恰到好处的力竭",
                            "url": "https://www.bilibili.com/video/BV1z4oWB3Ex9",
                            "author": "初夏ChuXXia",
                            "published_at": "2026-04-22 11:57:57",
                        }
                    ],
                }
            ],
        )

        monkeypatch.setattr(
            DingTalkWebhookService,
            "_fetch_bilibili_video_detail_by_url",
            lambda self, url: {
                "author": "初夏ChuXXia",
                "published_at_text": "2026-04-22 11:57:57",
                "like_count": 3689,
                "reply_count": 206,
                "view_count": 61317,
                "cover_image_url": "https://i0.hdslb.com/demo.jpg",
            },
        )

        requests: list[dict[str, object]] = []

        def fake_sender(
            webhook: str,
            payload: dict[str, object],
            timeout_seconds: float,
            secret: str | None,
        ) -> None:
            requests.append(payload)

        service = DingTalkWebhookService(
            session=session,
            settings=Settings(
                dingtalk_webhook="https://oapi.dingtalk.com/robot/send?access_token=test-token",
                enable_dingtalk_notifier=True,
            ),
            sender=fake_sender,
        )

        assert service.notify_job_summary(job) is True
        assert len(requests) == 1
        markdown_text = requests[0]["markdown"]["text"]
        assert requests[0]["markdown"]["title"] == "热点报告 初夏ChuXXia"
        assert "1. [PRAGMATA/识质存在：恰到好处的力竭](https://www.bilibili.com/video/BV1z4oWB3Ex9)" in markdown_text
        assert (
            "发布时间：2026-04-22 11:57 | 点赞：3689 | 评论：206 | 播放：61317"
            in markdown_text
        )
        assert "封面图：https://i0.hdslb.com/demo.jpg" in markdown_text


def test_dingtalk_webhook_service_prefers_persisted_stats_without_detail_refetch(tmp_path, monkeypatch) -> None:
    session_factory = setup_database(tmp_path, "dingtalk-webhook-persisted-stats.db")

    with session_factory() as session:
        source = create_source(session, "B站UP-4186021-视频投稿", "https://space.bilibili.com/4186021")
        source.collection_strategy = "bilibili_profile_videos_recent"
        job = JobService(session).create_manual_job()
        ReportService(session).generate_for_job(
            job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "持久化统计视频",
                            "url": "https://www.bilibili.com/video/BV1z4oWB3Ex9",
                            "author": "初夏ChuXXia",
                            "published_at": "2026-04-22 11:57:57",
                            "cover_image_url": "https://i0.hdslb.com/persisted.jpg",
                            "like_count": 3689,
                            "reply_count": 206,
                            "view_count": 61317,
                        }
                    ],
                }
            ],
        )

        def fail_fetch(self, url):
            raise AssertionError("should not refetch bilibili detail when counts are already persisted")

        monkeypatch.setattr(DingTalkWebhookService, "_fetch_bilibili_video_detail_by_url", fail_fetch)

        requests: list[dict[str, object]] = []

        def fake_sender(
            webhook: str,
            payload: dict[str, object],
            timeout_seconds: float,
            secret: str | None,
        ) -> None:
            requests.append(payload)

        service = DingTalkWebhookService(
            session=session,
            settings=Settings(
                dingtalk_webhook="https://oapi.dingtalk.com/robot/send?access_token=test-token",
                enable_dingtalk_notifier=True,
            ),
            sender=fake_sender,
        )

        assert service.notify_job_summary(job) is True
        markdown_text = requests[0]["markdown"]["text"]
        assert "点赞：3689 | 评论：206 | 播放：61317" in markdown_text
        assert "1. [持久化统计视频](https://www.bilibili.com/video/BV1z4oWB3Ex9)" in markdown_text
        assert "封面图：https://i0.hdslb.com/persisted.jpg" in markdown_text


def test_dingtalk_webhook_service_does_not_duplicate_hot_report_prefix_when_label_already_has_it(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "dingtalk-webhook-hot-report-prefix.db")

    with session_factory() as session:
        source = create_source(session, "热点报告 初夏ChuXXia", "https://example.com/source")
        job = JobService(session).create_manual_job()
        ReportService(session).generate_for_job(
            job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "普通帖子",
                            "url": "https://example.com/post-1",
                            "published_at": "2026-04-22 11:57:57",
                        }
                    ],
                }
            ],
        )

        requests: list[dict[str, object]] = []

        def fake_sender(
            webhook: str,
            payload: dict[str, object],
            timeout_seconds: float,
            secret: str | None,
        ) -> None:
            requests.append(payload)

        service = DingTalkWebhookService(
            session=session,
            settings=Settings(
                dingtalk_webhook="https://oapi.dingtalk.com/robot/send?access_token=test-token",
                enable_dingtalk_notifier=True,
            ),
            sender=fake_sender,
        )

        assert service.notify_job_summary(job) is True
        assert requests[0]["markdown"]["title"] == "热点报告 初夏ChuXXia"


def test_dingtalk_webhook_service_adds_signature_query_when_secret_is_configured(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "dingtalk-webhook-signature.db")

    with session_factory() as session:
        source = create_source(session, "游戏频道", "https://example.com/source-a")
        job = JobService(session).create_manual_job()
        ReportService(session).generate_for_job(
            job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "新帖子1",
                            "url": "https://example.com/post-new-1",
                            "published_at": "2026-03-24 10:00",
                        }
                    ],
                }
            ],
        )

        captured: dict[str, object] = {}

        def fake_sender(
            webhook: str,
            payload: dict[str, object],
            timeout_seconds: float,
            secret: str | None,
        ) -> None:
            captured["webhook"] = webhook
            captured["payload"] = payload
            captured["timeout_seconds"] = timeout_seconds
            captured["secret"] = secret

        service = DingTalkWebhookService(
            session=session,
            settings=Settings(
                dingtalk_webhook="https://oapi.dingtalk.com/robot/send?access_token=test-token",
                dingtalk_secret="SECsignature",
                dingtalk_keyword="热点报告",
                enable_dingtalk_notifier=True,
            ),
            sender=fake_sender,
        )

        service.notify_job_summary(job)

        parsed = urlparse(str(captured["webhook"]))
        query = parse_qs(parsed.query)
        assert query["access_token"] == ["test-token"]
        assert "timestamp" in query
        assert "sign" in query



def test_dingtalk_webhook_service_reports_skip_reason_when_disabled(tmp_path) -> None:
    session_factory = setup_database(tmp_path, 'dingtalk-webhook-disabled.db')

    with session_factory() as session:
        job = JobService(session).create_manual_job()
        service = DingTalkWebhookService(
            session=session,
            settings=Settings(
                dingtalk_webhook='https://oapi.dingtalk.com/robot/send?access_token=test-token',
                enable_dingtalk_notifier=False,
            ),
        )

        assert service.get_skip_reason() == 'ENABLE_DINGTALK_NOTIFIER is false'
        assert service.notify_job_summary(job) is False


def test_dingtalk_webhook_service_skips_when_current_job_has_no_new_items(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "dingtalk-webhook-no-new-items.db")

    with session_factory() as session:
        source = create_source(session, "游戏频道", "https://example.com/source-a")
        first_job = JobService(session).create_manual_job()
        second_job = JobService(session).create_manual_job()
        report_service = ReportService(session)

        report_service.generate_for_job(
            first_job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "持续命中帖子",
                            "url": "https://example.com/post-keep",
                            "published_at": "2026-03-24 09:00",
                        }
                    ],
                }
            ],
        )
        report_service.generate_for_job(
            second_job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "持续命中帖子",
                            "url": "https://example.com/post-keep",
                            "published_at": "2026-03-24 09:00",
                        }
                    ],
                }
            ],
        )

        requests: list[dict[str, object]] = []

        def fake_sender(
            webhook: str,
            payload: dict[str, object],
            timeout_seconds: float,
            secret: str | None,
        ) -> None:
            requests.append(
                {
                    "webhook": webhook,
                    "payload": payload,
                    "timeout_seconds": timeout_seconds,
                    "secret": secret,
                }
            )

        service = DingTalkWebhookService(
            session=session,
            settings=Settings(
                dingtalk_webhook="https://oapi.dingtalk.com/robot/send?access_token=test-token",
                dingtalk_secret="SECtest",
                dingtalk_keyword="热点报告",
                enable_dingtalk_notifier=True,
            ),
            sender=fake_sender,
        )

        assert service.notify_job_summary(second_job) is False
        assert requests == []
        assert service.get_skip_reason() == "no new collected items in current job"


def test_dingtalk_webhook_service_preserves_date_only_published_at_without_midnight_display(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "dingtalk-webhook-date-only.db")

    with session_factory() as session:
        source = create_source(session, "日期频道", "https://example.com/source-date-only")
        job = JobService(session).create_manual_job()
        ReportService(session).generate_for_job(
            job,
            [
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "items": [
                        {
                            "title": "只有日期的通知帖子",
                            "url": "https://example.com/date-only-post",
                            "published_at": "2026-03-24",
                        }
                    ],
                }
            ],
        )

        requests: list[dict[str, object]] = []

        def fake_sender(
            webhook: str,
            payload: dict[str, object],
            timeout_seconds: float,
            secret: str | None,
        ) -> None:
            requests.append(payload)

        service = DingTalkWebhookService(
            session=session,
            settings=Settings(
                dingtalk_webhook="https://oapi.dingtalk.com/robot/send?access_token=test-token",
                enable_dingtalk_notifier=True,
            ),
            sender=fake_sender,
        )

        assert service.notify_job_summary(job) is True
        assert len(requests) == 1
        markdown_text = requests[0]["markdown"]["text"]
        assert "发布时间：2026-03-24" in markdown_text
        assert "发布时间：2026-03-24 00:00" not in markdown_text


