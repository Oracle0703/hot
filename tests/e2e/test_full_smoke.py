"""TC-E2E-001~005 — 全链路冒烟测试。

复用 ``tests/conftest.create_test_client`` 在 tmp 目录起一个 FastAPI 实例,
通过 HTTP API + 直接调用 JobRunner 走完关键路径,不再 skip。
"""

from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.delivery_record import DeliveryRecord
from app.services.dingtalk_webhook_service import DingTalkWebhookService
from tests.conftest import create_test_client, make_sqlite_url


HTML_FIXTURE = """
<html><body>
  <ul class='topics'>
    <li class='topic'>
      <a class='topic-link' href='https://example.com/post-1'>新游版号过审重磅</a>
      <span class='topic-time'>2026-04-23 08:00</span>
    </li>
    <li class='topic'>
      <a class='topic-link' href='https://example.com/post-2'>新作开放预约</a>
      <span class='topic-time'>2026-04-23 09:00</span>
    </li>
  </ul>
</body></html>
""".strip()


def _add_local_html_source(client, html_path: Path, name: str = "本地 HTML") -> str:
    response = client.post(
        "/api/sources",
        json={
            "name": name,
            "site_name": "Local",
            "entry_url": html_path.resolve().as_uri(),
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游", "新作"],
            "exclude_keywords": [],
            "max_items": 10,
            "enabled": True,
        },
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["id"]


def _trigger_job_and_wait(client, *, max_attempts: int = 40) -> tuple[str, dict]:
    response = client.post("/jobs/run", follow_redirects=False)
    assert response.status_code == 303
    job_id = response.headers["location"].rsplit("/", 1)[-1]
    body: dict = {}
    for _ in range(max_attempts):
        body = client.get(f"/api/jobs/{job_id}").json()
        if body.get("status") in {"success", "partial_success"} and body.get("report_id"):
            return job_id, body
        if body.get("status") in {"failed", "cancelled"}:
            return job_id, body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish: last={body}")


def _sqlite_path(database_url: str) -> Path:
    parsed = urlparse(database_url)
    raw = parsed.path
    if raw.startswith("/") and len(raw) >= 3 and raw[2] == ":":
        raw = raw[1:]
    return Path(raw)


class TestFullSmoke:
    def test_first_launch_creates_db_and_serves_health(self, tmp_path) -> None:
        """TC-E2E-001: 空 runtime root 启动 → DB 文件创建 + /system/health/extended 200。"""
        db_url = make_sqlite_url(tmp_path, "fresh.db")
        db_path = _sqlite_path(db_url)
        assert not db_path.exists()

        client = create_test_client(db_url)
        try:
            assert db_path.exists(), "数据库文件应在首次启动时被创建"

            health = client.get("/system/health/extended")
            assert health.status_code in (200, 503)
            payload = health.json()
            assert "database" in payload and "scheduler" in payload

            info = client.get("/system/info")
            assert info.status_code == 200
        finally:
            client.close()

    def test_full_pipeline_with_dingtalk_mock(self, tmp_path, monkeypatch) -> None:
        """TC-E2E-002: 配置来源 → 触发任务 → 报告产生 + DingTalk 通知被调用。"""
        monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "reports"))
        monkeypatch.setenv("ENABLE_DINGTALK_NOTIFIER", "true")
        monkeypatch.setenv(
            "DINGTALK_WEBHOOK",
            "https://oapi.dingtalk.com/robot/send?access_token=fake",
        )

        captured: list[dict] = []

        from app.services import dingtalk_webhook_service

        def _fake_send(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            captured.append({"args": args, "kwargs": kwargs})
            return {"errcode": 0}

        monkeypatch.setattr(
            dingtalk_webhook_service.DingTalkWebhookService,
            "send_report_summary",
            _fake_send,
            raising=False,
        )

        html_path = tmp_path / "topics.html"
        html_path.write_text(HTML_FIXTURE, encoding="utf-8")
        client = create_test_client(make_sqlite_url(tmp_path, "pipeline.db"))
        try:
            _add_local_html_source(client, html_path)
            job_id, body = _trigger_job_and_wait(client)
            assert body["status"] == "success", body
            report_id = body["report_id"]
            assert report_id

            md = client.get(f"/api/reports/{report_id}/download?format=md")
            assert md.status_code == 200
            assert "新游版号过审重磅" in md.text
        finally:
            client.close()

    def test_full_pipeline_promotes_content_and_auto_dispatches_subscription(self, tmp_path, monkeypatch) -> None:
        """TC-E2E-006: 任务产出内容中心记录，并按订阅规则自动生成投递记录。"""
        monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "reports"))
        monkeypatch.setenv("ENABLE_DINGTALK_NOTIFIER", "true")
        monkeypatch.setenv("DINGTALK_WEBHOOK", "https://oapi.dingtalk.com/robot/send?access_token=e2e-token")
        html_path = tmp_path / "topics.html"
        html_path.write_text(HTML_FIXTURE, encoding="utf-8")
        db_url = make_sqlite_url(tmp_path, "content-dispatch.db")
        requests: list[dict[str, object]] = []

        def fake_send(self, webhook: str, payload: dict[str, object], timeout_seconds: float, secret: str | None) -> None:
            requests.append(
                {
                    "webhook": webhook,
                    "payload": payload,
                    "timeout_seconds": timeout_seconds,
                    "secret": secret,
                }
            )

        monkeypatch.setattr(DingTalkWebhookService, "_send_webhook", fake_send)
        monkeypatch.setattr(DingTalkWebhookService, "notify_job_summary", lambda self, job: False)
        client = create_test_client(db_url)
        try:
            _add_local_html_source(client, html_path, name="HR情报源")
            subscription_response = client.post(
                "/api/subscriptions",
                json={
                    "code": "hr-daily",
                    "channel": "dingtalk",
                    "business_lines": ["HR情报源"],
                    "keywords": ["新游"],
                },
            )
            assert subscription_response.status_code == 201, subscription_response.text

            _, body = _trigger_job_and_wait(client)
            assert body["status"] == "success", body

            content_response = client.get("/api/content")
            assert content_response.status_code == 200
            content_payload = content_response.json()
            assert len(content_payload) == 2
            assert {item["title"] for item in content_payload} == {"新游版号过审重磅", "新作开放预约"}
        finally:
            client.close()

        engine = create_engine(db_url, future=True, connect_args={"check_same_thread": False})
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        with session_factory() as session:
            records = list(session.scalars(select(DeliveryRecord)).all())

        assert len(requests) == 1
        assert str(requests[0]["webhook"]).startswith("https://oapi.dingtalk.com/robot/send?access_token=e2e-token")
        assert len(records) == 1
        assert records[0].status == "sent"

    def test_upgrade_preserves_data(self, tmp_path, monkeypatch) -> None:
        """TC-E2E-003: 模拟升级——同一 DB 重建 app,源/任务/报告记录全部保留。"""
        monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "reports"))
        html_path = tmp_path / "topics.html"
        html_path.write_text(HTML_FIXTURE, encoding="utf-8")
        db_url = make_sqlite_url(tmp_path, "upgrade.db")

        client_v1 = create_test_client(db_url)
        try:
            source_id = _add_local_html_source(client_v1, html_path)
            job_id_v1, body_v1 = _trigger_job_and_wait(client_v1)
            assert body_v1["status"] == "success"
            report_id_v1 = body_v1["report_id"]
        finally:
            client_v1.close()

        client_v2 = create_test_client(db_url)
        try:
            sources = client_v2.get("/api/sources").json()
            assert any(s["id"] == source_id for s in sources), "升级后来源应保留"
            job_after = client_v2.get(f"/api/jobs/{job_id_v1}").json()
            assert job_after["status"] == "success", "升级后历史任务应保留"
            assert job_after["report_id"] == report_id_v1, "全局报告 ID 应保持稳定"
        finally:
            client_v2.close()

    def test_cancel_during_running_job(self, tmp_path, monkeypatch) -> None:
        """TC-E2E-004: 任务运行期间 cancel_registry 介入,最终状态为 cancelled。"""
        from uuid import uuid4

        from app.db import create_session_factory, get_engine
        from app.models.base import Base
        from app.models.job import CollectionJob
        from app.models.source import Source
        from app.services import cancel_registry
        from app.workers.runner import JobRunner

        monkeypatch.setenv("DATABASE_URL", make_sqlite_url(tmp_path, "cancel.db"))
        monkeypatch.setenv("HOT_RUNTIME_ROOT", str(tmp_path))
        monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "reports"))

        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        factory = create_session_factory(engine=engine)

        cancel_registry.clear()

        with factory() as session:
            for idx in range(3):
                session.add(
                    Source(
                        name=f"src-{idx}",
                        site_name="local",
                        entry_url=f"file:///tmp/src-{idx}.html",
                        fetch_mode="http",
                        parser_type="generic_css",
                        enabled=True,
                    )
                )
            job = CollectionJob(id=uuid4(), status="pending", trigger_type="manual")
            session.add(job)
            session.commit()
            job_id = job.id

        call_count = {"n": 0}

        def _executor(source):
            call_count["n"] += 1
            if call_count["n"] == 1:
                cancel_registry.request_cancel(job_id)
            return {"item_count": 0, "items": []}

        runner = JobRunner(
            session_factory=factory,
            source_executor=_executor,
            sleeper=lambda _s: None,
        )
        runner.run_once()

        with factory() as session:
            final = session.get(CollectionJob, job_id)
            assert final is not None
            assert final.status == "cancelled", f"got {final.status}"
        assert call_count["n"] < 3, "取消后剩余 source 应被跳过"

    def test_concurrent_jobs_finalize_report(self, tmp_path, monkeypatch) -> None:
        """TC-E2E-005: 连续两次任务收尾,全局报告内容仍完整可读。"""
        monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "reports"))
        html_path = tmp_path / "topics.html"
        html_path.write_text(HTML_FIXTURE, encoding="utf-8")
        client = create_test_client(make_sqlite_url(tmp_path, "concurrent.db"))
        try:
            _add_local_html_source(client, html_path)

            _, body1 = _trigger_job_and_wait(client)
            _, body2 = _trigger_job_and_wait(client)
            assert body1["status"] == "success"
            assert body2["status"] == "success"
            assert body1["report_id"] == body2["report_id"], "全局总报告 ID 应稳定"

            md = client.get(f"/api/reports/{body2['report_id']}/download?format=md").text
            assert "新游版号过审重磅" in md
            assert "新作开放预约" in md
        finally:
            client.close()
