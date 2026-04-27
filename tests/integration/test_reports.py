import time
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select

from app.api.routes_sources import SessionFactoryHolder
from app.models.item import CollectedItem
from app.models.source import Source
from tests.conftest import create_test_client, make_sqlite_url


HTML_SOURCE = """
<html>
  <body>
    <ul class='topics'>
      <li class='topic'>
        <a class='topic-link' href='https://example.com/post-1'>重磅新游版号过审</a>
        <span class='topic-time'>2026-03-24 08:00</span>
      </li>
    </ul>
  </body>
</html>
""".strip()


def as_uuid(value: str) -> UUID:
    return UUID(value)


def _run_job_and_wait_for_report(client, *, max_attempts: int = 20) -> tuple[str, str]:
    run_response = client.post("/jobs/run", follow_redirects=False)
    job_id = run_response.headers["location"].rsplit("/", 1)[-1]

    report_id = None
    for _ in range(max_attempts):
        job_response = client.get(f"/api/jobs/{job_id}")
        body = job_response.json()
        report_id = body["report_id"]
        if body["status"] == "success" and report_id:
            return job_id, report_id
        time.sleep(0.05)

    raise AssertionError(f"job {job_id} did not finish successfully")


def test_reports_page_lists_generated_report_and_download_works(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_DEBUG", "true")
    monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "reports"))
    html_path = Path(tmp_path) / "topics.html"
    html_path.write_text(HTML_SOURCE, encoding="utf-8")
    client = create_test_client(make_sqlite_url(tmp_path, "reports-page.db"))
    client.post(
        "/api/sources",
        json={
            "name": "本地 HTML",
            "site_name": "Local",
            "entry_url": html_path.resolve().as_uri(),
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 10,
            "enabled": True,
        },
    )

    run_response = client.post("/jobs/run", follow_redirects=False)
    job_id = run_response.headers["location"].rsplit("/", 1)[-1]

    report_id = None
    for _ in range(20):
        job_response = client.get(f"/api/jobs/{job_id}")
        body = job_response.json()
        report_id = body["report_id"]
        if body["status"] == "success" and report_id:
            break
        time.sleep(0.05)

    reports_page = client.get("/reports")
    assert reports_page.status_code == 200
    assert "历史报告" in reports_page.text
    assert "body class='app-shell theme-dark'" in reports_page.text
    assert "app-shell" in reports_page.text
    assert "panel" in reports_page.text
    assert report_id in reports_page.text

    report_detail = client.get(f"/reports/{report_id}")
    assert report_detail.status_code == 200
    assert "报告预览" in report_detail.text
    assert "body class='app-shell theme-dark'" in report_detail.text
    assert "app-shell" in report_detail.text
    assert "panel" in report_detail.text
    assert "重磅新游版号过审" in report_detail.text
    assert "返回首页" in report_detail.text
    assert "href='/'" in report_detail.text

    markdown_download = client.get(f"/api/reports/{report_id}/download?format=md")
    docx_download = client.get(f"/api/reports/{report_id}/download?format=docx")

    assert markdown_download.status_code == 200
    assert "重磅新游版号过审" in markdown_download.text
    assert docx_download.status_code == 200
    assert docx_download.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument")


def test_reports_page_shows_single_global_report_after_two_runs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_DEBUG", "true")
    monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "reports"))
    html_path = Path(tmp_path) / "topics.html"
    html_path.write_text(HTML_SOURCE, encoding="utf-8")
    client = create_test_client(make_sqlite_url(tmp_path, "reports-global-page.db"))
    client.post(
        "/api/sources",
        json={
            "name": "本地 HTML",
            "site_name": "Local",
            "entry_url": html_path.resolve().as_uri(),
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 10,
            "enabled": True,
        },
    )

    _, first_report_id = _run_job_and_wait_for_report(client)
    _, second_report_id = _run_job_and_wait_for_report(client)

    reports_page = client.get("/reports")

    assert first_report_id == second_report_id
    assert reports_page.status_code == 200
    assert "全局热点总报告" in reports_page.text
    assert "body class='app-shell theme-dark'" in reports_page.text
    assert reports_page.text.count(f"href='/reports/{first_report_id}'") == 1


def test_reports_page_can_clear_collected_items_for_crawl_testing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_DEBUG", "true")
    monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "reports"))
    html_path = Path(tmp_path) / "topics.html"
    html_path.write_text(HTML_SOURCE, encoding="utf-8")
    client = create_test_client(make_sqlite_url(tmp_path, "reports-clear-items.db"))
    client.post(
        "/api/sources",
        json={
            "name": "本地 HTML",
            "site_name": "Local",
            "entry_url": html_path.resolve().as_uri(),
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 10,
            "enabled": True,
        },
    )
    _, report_id = _run_job_and_wait_for_report(client)

    reports_page = client.get("/reports")

    assert reports_page.status_code == 200
    assert "清空已采集内容" in reports_page.text
    assert "action='/reports/clear-items'" in reports_page.text

    response = client.post("/reports/clear-items", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/reports?cleared=1&cleared_count=1"

    cleared_page = client.get(response.headers["location"])
    assert cleared_page.status_code == 200
    assert "已清空 1 条已采集内容" in cleared_page.text
    assert f"/reports/{report_id}" in cleared_page.text

    with SessionFactoryHolder.factory() as session:
        item_count = session.scalar(select(func.count()).select_from(CollectedItem))

    assert item_count == 0


def test_weekly_page_lists_recent_week_items_in_requested_columns(tmp_path, monkeypatch) -> None:
    database_url = make_sqlite_url(tmp_path, "weekly-page.db")
    client = create_test_client(database_url)
    now = datetime(2026, 4, 23, 20, 0, 0)

    from app.api import routes_reports

    class FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls) -> datetime:
            return now

    monkeypatch.setattr(routes_reports, "datetime", FrozenDateTime)

    with SessionFactoryHolder.factory() as session:
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
        session.add_all(
            [
                CollectedItem(
                    source_id=source.id,
                    job_id=as_uuid("66666666-6666-6666-6666-666666666666"),
                    first_seen_job_id=as_uuid("66666666-6666-6666-6666-666666666666"),
                    last_seen_job_id=as_uuid("66666666-6666-6666-6666-666666666666"),
                    title="周内视频一",
                    url="https://www.bilibili.com/video/BV1TEST111/",
                    published_at=now - timedelta(hours=1),
                    published_at_text="2026-04-23 19:00:00",
                    first_seen_at=now - timedelta(days=1),
                    last_seen_at=now - timedelta(days=1),
                    cover_image_url="https://example.com/cover-1.jpg",
                    like_count=137,
                    view_count=3356,
                    reply_count=53,
                    normalized_hash="weekly-hash-1",
                ),
                CollectedItem(
                    source_id=source.id,
                    job_id=as_uuid("77777777-7777-7777-7777-777777777777"),
                    first_seen_job_id=as_uuid("77777777-7777-7777-7777-777777777777"),
                    last_seen_job_id=as_uuid("77777777-7777-7777-7777-777777777777"),
                    title="周内视频二",
                    url="https://www.bilibili.com/video/BV1TEST222/",
                    published_at=now - timedelta(days=2),
                    published_at_text="2026-04-21 10:30:00",
                    first_seen_at=now - timedelta(days=2),
                    last_seen_at=now - timedelta(days=2),
                    like_count=88,
                    view_count=1200,
                    reply_count=11,
                    normalized_hash="weekly-hash-2",
                ),
                CollectedItem(
                    source_id=source.id,
                    job_id=as_uuid("88888888-8888-8888-8888-888888888888"),
                    first_seen_job_id=as_uuid("88888888-8888-8888-8888-888888888888"),
                    last_seen_job_id=as_uuid("88888888-8888-8888-8888-888888888888"),
                    title="超过一周的视频",
                    url="https://www.bilibili.com/video/BV1TEST333/",
                    published_at=now - timedelta(days=8),
                    published_at_text="2026-04-15 09:00:00",
                    first_seen_at=now - timedelta(days=8),
                    last_seen_at=now - timedelta(days=8),
                    cover_image_url="https://example.com/cover-3.jpg",
                    like_count=1,
                    view_count=2,
                    reply_count=3,
                    normalized_hash="weekly-hash-3",
                ),
            ]
        )
        session.commit()

    response = client.get("/weekly")

    assert response.status_code == 200
    assert "最近一周热点" in response.text
    assert "序号" in response.text
    assert "标题" in response.text
    assert "封面预览图" in response.text
    assert "点赞数" in response.text
    assert "播放量" in response.text
    assert "评论数" in response.text
    assert "发布时间" in response.text
    assert "当前推送阈值" in response.text
    assert "/config?return_to=weekly" in response.text
    assert "WEEKLY_GRADE_PUSH_THRESHOLD" in response.text
    assert "周内视频一" in response.text
    assert "https://www.bilibili.com/video/BV1TEST111/" in response.text
    assert "img" in response.text
    assert "/weekly/covers/" in response.text
    assert "https://example.com/cover-1.jpg" not in response.text
    assert "2026-04-23 19:00" in response.text
    assert "周内视频二" in response.text
    assert "暂无封面" in response.text
    assert "超过一周的视频" not in response.text


def test_weekly_page_does_not_persist_recommended_grade_on_get(tmp_path, monkeypatch) -> None:
    database_url = make_sqlite_url(tmp_path, "weekly-page-readonly.db")
    client = create_test_client(database_url)
    now = datetime(2026, 4, 23, 20, 0, 0)

    from app.api import routes_reports

    class FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls) -> datetime:
            return now

    monkeypatch.setattr(routes_reports, "datetime", FrozenDateTime)

    with SessionFactoryHolder.factory() as session:
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
        item = CollectedItem(
            source_id=source.id,
            job_id=as_uuid("99999999-9999-9999-9999-999999999999"),
            first_seen_job_id=as_uuid("99999999-9999-9999-9999-999999999999"),
            last_seen_job_id=as_uuid("99999999-9999-9999-9999-999999999999"),
            title="只读推荐分视频",
            url="https://www.bilibili.com/video/BV1READONLY/",
            published_at=now - timedelta(hours=1),
            published_at_text="2026-04-23 19:00:00",
            first_seen_at=now - timedelta(hours=2),
            last_seen_at=now - timedelta(hours=2),
            like_count=300,
            view_count=20000,
            reply_count=120,
            normalized_hash="weekly-readonly-grade-1",
        )
        session.add(item)
        session.commit()
        item_id = str(item.id)

    response = client.get("/weekly")

    assert response.status_code == 200
    assert "只读推荐分视频" in response.text
    assert ">A<" in response.text

    with SessionFactoryHolder.factory() as session:
        item = session.get(CollectedItem, UUID(item_id))

    assert item is not None
    assert item.recommended_grade is None


def test_weekly_page_supports_saving_manual_grades_and_batch_pushing(tmp_path, monkeypatch) -> None:
    database_url = make_sqlite_url(tmp_path, "weekly-rating-push-page.db")
    client = create_test_client(database_url)
    now = datetime(2026, 4, 23, 20, 0, 0)
    monkeypatch.setenv("ENABLE_DINGTALK_NOTIFIER", "true")
    monkeypatch.setenv("DINGTALK_WEBHOOK", "https://oapi.dingtalk.com/robot/send?access_token=test-token")
    monkeypatch.setenv("WEEKLY_GRADE_PUSH_THRESHOLD", "B+")

    from app.api import routes_reports
    from app.services import weekly_dingtalk_push_service

    class FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls) -> datetime:
            return now

    requests: list[dict[str, object]] = []

    def fake_sender(webhook: str, payload: dict[str, object], timeout_seconds: float, secret: str | None) -> None:
        requests.append({"webhook": webhook, "payload": payload})

    monkeypatch.setattr(routes_reports, "datetime", FrozenDateTime)
    monkeypatch.setattr(weekly_dingtalk_push_service, "datetime", FrozenDateTime)
    monkeypatch.setattr(weekly_dingtalk_push_service.WeeklyDingTalkPushService, "_send", staticmethod(fake_sender))

    with SessionFactoryHolder.factory() as session:
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
        first_item = CollectedItem(
            source_id=source.id,
            job_id=as_uuid("11111111-1111-1111-1111-111111111111"),
            first_seen_job_id=as_uuid("11111111-1111-1111-1111-111111111111"),
            last_seen_job_id=as_uuid("11111111-1111-1111-1111-111111111111"),
            title="可推送视频",
            url="https://www.bilibili.com/video/BV1RATE111/",
            published_at=now - timedelta(hours=1),
            published_at_text="2026-04-23 19:00:00",
            first_seen_at=now - timedelta(days=1),
            last_seen_at=now - timedelta(days=1),
            cover_image_url="https://example.com/cover-1.jpg",
            like_count=300,
            view_count=20000,
            reply_count=120,
            normalized_hash="weekly-rating-push-1",
        )
        second_item = CollectedItem(
            source_id=source.id,
            job_id=as_uuid("22222222-2222-2222-2222-222222222222"),
            first_seen_job_id=as_uuid("22222222-2222-2222-2222-222222222222"),
            last_seen_job_id=as_uuid("22222222-2222-2222-2222-222222222222"),
            title="不推送视频",
            url="https://www.bilibili.com/video/BV1RATE222/",
            published_at=now - timedelta(hours=2),
            published_at_text="2026-04-23 18:00:00",
            first_seen_at=now - timedelta(days=1),
            last_seen_at=now - timedelta(days=1),
            like_count=30,
            view_count=5000,
            reply_count=10,
            normalized_hash="weekly-rating-push-2",
        )
        session.add_all([first_item, second_item])
        session.commit()
        first_item_id = str(first_item.id)
        second_item_id = str(second_item.id)

    save_response = client.post(
        "/weekly/ratings",
        content=f"grade_{first_item_id}=A&grade_{second_item_id}=B",
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )

    assert save_response.status_code == 303
    assert save_response.headers["location"] == "/weekly?ratings_saved=1"

    with SessionFactoryHolder.factory() as session:
        first_item = session.get(CollectedItem, UUID(first_item_id))
        second_item = session.get(CollectedItem, UUID(second_item_id))
        assert first_item is not None
        assert second_item is not None
        assert first_item.manual_grade == "A"
        assert second_item.manual_grade == "B"

    push_response = client.post("/weekly/push", follow_redirects=False)

    assert push_response.status_code == 303
    assert push_response.headers["location"] == "/weekly?pushed_count=1"
    assert len(requests) == 1
    assert "[可推送视频](https://www.bilibili.com/video/BV1RATE111/)" in requests[0]["payload"]["markdown"]["text"]
    assert "不推送视频" not in requests[0]["payload"]["markdown"]["text"]

    weekly_page = client.get("/weekly")
    assert "当前推送阈值" in weekly_page.text
    assert "批量设为" in weekly_page.text
    assert "清空本页评分" in weekly_page.text

    with SessionFactoryHolder.factory() as session:
        first_item = session.get(CollectedItem, UUID(first_item_id))
        second_item = session.get(CollectedItem, UUID(second_item_id))
        assert first_item is not None
        assert second_item is not None
        assert first_item.pushed_to_dingtalk_at is not None
        assert second_item.pushed_to_dingtalk_at is None


def test_weekly_page_push_shows_empty_feedback_when_no_item_matches_threshold(tmp_path, monkeypatch) -> None:
    database_url = make_sqlite_url(tmp_path, "weekly-rating-push-empty-page.db")
    client = create_test_client(database_url)
    now = datetime(2026, 4, 23, 20, 0, 0)
    monkeypatch.setenv("ENABLE_DINGTALK_NOTIFIER", "true")
    monkeypatch.setenv("DINGTALK_WEBHOOK", "https://oapi.dingtalk.com/robot/send?access_token=test-token")
    monkeypatch.setenv("WEEKLY_GRADE_PUSH_THRESHOLD", "A")

    from app.api import routes_reports
    from app.services import weekly_dingtalk_push_service

    class FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls) -> datetime:
            return now

    pushed_requests: list[dict[str, object]] = []

    def fake_sender(webhook: str, payload: dict[str, object], timeout_seconds: float, secret: str | None) -> None:
        pushed_requests.append({"webhook": webhook, "payload": payload})

    monkeypatch.setattr(routes_reports, "datetime", FrozenDateTime)
    monkeypatch.setattr(weekly_dingtalk_push_service, "datetime", FrozenDateTime)
    monkeypatch.setattr(weekly_dingtalk_push_service.WeeklyDingTalkPushService, "_send", staticmethod(fake_sender))

    with SessionFactoryHolder.factory() as session:
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
        item = CollectedItem(
            source_id=source.id,
            job_id=as_uuid("33333333-3333-3333-3333-333333333333"),
            first_seen_job_id=as_uuid("33333333-3333-3333-3333-333333333333"),
            last_seen_job_id=as_uuid("33333333-3333-3333-3333-333333333333"),
            title="未达阈值视频",
            url="https://www.bilibili.com/video/BV1RATE333/",
            published_at=now - timedelta(hours=3),
            published_at_text="2026-04-23 17:00:00",
            first_seen_at=now - timedelta(days=1),
            last_seen_at=now - timedelta(days=1),
            like_count=30,
            view_count=5000,
            reply_count=10,
            manual_grade="B+",
            normalized_hash="weekly-rating-push-empty-1",
        )
        session.add(item)
        session.commit()

    push_response = client.post("/weekly/push", follow_redirects=False)

    assert push_response.status_code == 303
    assert push_response.headers["location"] == "/weekly?push_empty=1"
    assert pushed_requests == []

    weekly_page = client.get(push_response.headers["location"])

    assert weekly_page.status_code == 200
    assert "当前没有达到阈值且未推送的内容。" in weekly_page.text


def test_weekly_page_shows_config_updated_feedback_with_current_settings(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WEEKLY_GRADE_PUSH_THRESHOLD", "A")
    monkeypatch.setenv("WEEKLY_COVER_CACHE_RETENTION_DAYS", "45")
    client = create_test_client(make_sqlite_url(tmp_path, "weekly-config-updated-page.db"))

    response = client.get("/weekly?config_updated=1")

    assert response.status_code == 200
    assert "周榜配置已更新。" in response.text
    assert "当前推送阈值为 A" in response.text
    assert "封面缓存保留 45 天" in response.text
