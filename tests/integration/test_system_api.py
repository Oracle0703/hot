"""TC-API-001~007 — /system/* endpoints integration tests.

See docs/specs/api-reference.md and docs/test-cases.md.
"""

from __future__ import annotations

import pytest

from tests.conftest import create_test_client, make_sqlite_url


def test_system_info_returns_all_fields(tmp_path) -> None:
    """TC-API-001: GET /system/info 返回 version/commit/built_at/python_version/runtime_root/uptime_seconds/app_name/app_env"""
    client = create_test_client(make_sqlite_url(tmp_path))

    response = client.get("/system/info")

    assert response.status_code == 200
    payload = response.json()
    expected_keys = {
        "version",
        "commit",
        "built_at",
        "channel",
        "python_version",
        "runtime_root",
        "started_at",
        "uptime_seconds",
        "app_name",
        "app_env",
        "debug",
    }
    assert expected_keys.issubset(payload.keys())
    assert payload["uptime_seconds"] >= 0


def test_system_health_extended_returns_status_and_issues(tmp_path) -> None:
    """TC-API-002: GET /system/health/extended 在 DB OK 时返回 200 + 含 database/scheduler/disk/issues 字段"""
    client = create_test_client(make_sqlite_url(tmp_path))

    response = client.get("/system/health/extended")

    assert response.status_code in (200, 503)
    payload = response.json()
    assert "database" in payload
    assert "scheduler" in payload
    assert "disk" in payload
    assert "issues" in payload
    assert isinstance(payload["issues"], list)


def test_cancel_running_job_returns_no_running_when_idle(tmp_path) -> None:
    """TC-API-004: POST /system/jobs/cancel-running 在无运行任务时返回 cancelled_job_id=null reason=no_running_job"""
    client = create_test_client(make_sqlite_url(tmp_path))

    response = client.post("/system/jobs/cancel-running", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["cancelled_job_id"] is None
    assert payload["reason"] == "no_running_job"


def test_config_export_default_masks_sensitive_fields(tmp_path, monkeypatch) -> None:
    """TC-API-006: GET /system/config/export?mask=true 默认脱敏，内容不含真实 Cookie/Secret"""
    monkeypatch.setenv("BILIBILI_COOKIE", "SESSDATA=verysecretvalue1234567890")
    monkeypatch.setenv("DINGTALK_SECRET", "shortsec")
    client = create_test_client(make_sqlite_url(tmp_path))

    response = client.get("/system/config/export")

    assert response.status_code == 200
    body = response.text
    assert "verysecretvalue1234567890" not in body
    assert "BILIBILI_COOKIE" in body
    # short secret 应被全部 ***
    assert "shortsec" not in body


def test_config_export_unmasked_in_production_forbidden(tmp_path, monkeypatch) -> None:
    """TC-API-007: GET /system/config/export?mask=false 在 APP_DEBUG=false 时返回 403"""
    monkeypatch.setenv("APP_DEBUG", "false")
    client = create_test_client(make_sqlite_url(tmp_path))

    response = client.get("/system/config/export?mask=false")

    assert response.status_code == 403


def test_health_extended_returns_503_on_db_failure(tmp_path, monkeypatch) -> None:
    """TC-API-003: DB 探活失败时返回 503 且 issues 含 DATABASE_UNREACHABLE。"""
    from sqlalchemy.exc import OperationalError

    db_url = make_sqlite_url(tmp_path)
    client = create_test_client(db_url)

    # 让 _check_database 永远返回失败,模拟 DB 不可达
    from app.api import routes_system
    monkeypatch.setattr(routes_system, "_check_database", lambda: (False, "OperationalError"))

    resp = client.get("/system/health/extended")
    assert resp.status_code == 503
    body = resp.json()
    codes = [issue.get("code") for issue in body.get("issues", [])]
    assert "DATABASE_UNREACHABLE" in codes


def test_cancel_running_job_returns_running_job_id(tmp_path) -> None:
    """TC-API-005: 数据库存在 status=running 任务时,接口返回该 job_id 并登记 cancel_registry"""
    from datetime import datetime
    from uuid import uuid4

    from sqlalchemy import create_engine

    from app.db import create_session_factory
    from app.models.job import CollectionJob
    from app.services import cancel_registry

    cancel_registry.clear()
    db_url = make_sqlite_url(tmp_path)
    client = create_test_client(db_url)
    engine = create_engine(db_url, future=True)
    factory = create_session_factory(engine=engine)

    job_id = uuid4()
    with factory() as session:
        session.add(
            CollectionJob(
                id=job_id,
                status="running",
                trigger_type="manual",
                started_at=datetime.utcnow(),
            )
        )
        session.commit()

    try:
        response = client.post("/system/jobs/cancel-running", json={})
        assert response.status_code == 200
        payload = response.json()
        assert payload["cancelled_job_id"] == str(job_id)
        assert payload["mode"] == "cooperative"
        assert cancel_registry.is_cancelled(job_id) is True

        # 重复取消返回 already_cancelled
        repeat = client.post("/system/jobs/cancel-running", json={})
        assert repeat.json()["reason"] == "already_cancelled"
    finally:
        cancel_registry.clear()
        engine.dispose()
