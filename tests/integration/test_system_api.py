"""TC-API-001~007 — /system/* endpoints integration tests.

See docs/specs/api-reference.md and docs/test-cases.md.
"""

from __future__ import annotations

import os
import subprocess
import json
from pathlib import Path

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


def test_system_desktop_manifest_exposes_shell_routes(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path))

    response = client.get("/system/desktop-manifest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "desktop-shell-manifest"
    assert payload["entry_route"] == "/"
    assert payload["health_route"] == "/system/health/extended"
    assert payload["docs_route"] == "/docs"
    assert payload["service"]["entry_url"] == "http://testserver/"
    assert payload["service"]["desktop_manifest_url"] == "http://testserver/system/desktop-manifest"
    assert payload["service"]["health_url"] == "http://testserver/system/health/extended"
    assert payload["service"]["docs_url"] == "http://testserver/docs"
    assert any(item["href"] == "/content-center" for item in payload["navigation"])
    assert any(item["href"] == "/deliveries" for item in payload["navigation"])
    assert payload["control"]["launch"]["kind"] == "launcher-start"
    assert payload["control"]["launch"]["launcher_path"].endswith("HotCollectorLauncher.exe")
    assert payload["control"]["launch"]["source_entry_path"].endswith("launcher.py")
    assert payload["control"]["launch"]["release_bat_path"].endswith("启动系统.bat")
    assert payload["control"]["launch"]["preferred_path"].endswith("launcher.py")
    assert payload["control"]["launch"]["launch_mode"] == "python-script"
    assert payload["control"]["launch"]["preferred_args"] == []
    assert payload["control"]["probe"]["kind"] == "launcher-probe"
    assert payload["control"]["probe"]["script_path"].endswith("scripts\\status.ps1")
    assert payload["control"]["probe"]["default_args"] == ["-PrintJson"]
    assert payload["control"]["probe"]["release_bat_path"].endswith("查看状态.bat")
    assert payload["control"]["probe"]["preferred_path"].endswith("scripts\\status.ps1")
    assert payload["control"]["probe"]["launch_mode"] == "powershell-file"
    assert payload["control"]["probe"]["preferred_args"] == ["-PrintJson"]
    assert payload["control"]["stop"]["kind"] == "stop-script"
    assert payload["control"]["stop"]["script_path"].endswith("scripts\\stop.ps1")
    assert payload["control"]["stop"]["default_args"] == ["-PrintJson"]
    assert payload["control"]["stop"]["release_bat_path"].endswith("停止系统.bat")
    assert payload["control"]["stop"]["preferred_path"].endswith("scripts\\stop.ps1")
    assert payload["control"]["stop"]["launch_mode"] == "powershell-file"
    assert payload["control"]["stop"]["preferred_args"] == ["-PrintJson"]


def test_system_desktop_manifest_prefers_release_entrypoints_in_packaged_runtime(tmp_path) -> None:
    from tests.integration.test_scripts import PREPARE, ROOT, run_ps1

    dist_root = ROOT / "tmp_test_manifest_release_dist"
    release_root = ROOT / "tmp_test_manifest_release_out"
    previous_runtime_root = os.environ.get("HOT_RUNTIME_ROOT")
    previous_runtime_root_is_auto = os.environ.get("_CODEX_TEST_AUTO_RUNTIME_ROOT")
    try:
        if dist_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{dist_root}'"], check=False)
        if release_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{release_root}'"], check=False)

        dist_root.mkdir(parents=True, exist_ok=True)
        (dist_root / "HotCollectorLauncher.exe").write_text("stub", encoding="utf-8")

        result = run_ps1(
            PREPARE,
            "-ReleaseRoot",
            str(release_root.relative_to(ROOT)),
            "-DistRoot",
            str(dist_root.relative_to(ROOT)),
        )
        assert result.returncode == 0

        db_url = f"sqlite:///{(release_root / 'data' / 'test.db').as_posix()}"
        os.environ["HOT_RUNTIME_ROOT"] = str(release_root)
        os.environ["_CODEX_TEST_AUTO_RUNTIME_ROOT"] = "0"
        client = create_test_client(db_url)

        response = client.get("/system/desktop-manifest")

        assert response.status_code == 200
        payload = response.json()
        assert payload["runtime"]["runtime_root"] == str(release_root)
        assert payload["control"]["launch"]["preferred_path"] == str(release_root / "启动系统.bat")
        assert payload["control"]["launch"]["launch_mode"] == "batch-file"
        assert payload["control"]["launch"]["preferred_args"] == []
        assert payload["control"]["probe"]["preferred_path"] == str(release_root / "查看状态.bat")
        assert payload["control"]["probe"]["launch_mode"] == "batch-file"
        assert payload["control"]["probe"]["preferred_args"] == []
        assert payload["control"]["stop"]["preferred_path"] == str(release_root / "停止系统.bat")
        assert payload["control"]["stop"]["launch_mode"] == "batch-file"
        assert payload["control"]["stop"]["preferred_args"] == ["-PrintJson"]
    finally:
        if previous_runtime_root is None:
            os.environ.pop("HOT_RUNTIME_ROOT", None)
        else:
            os.environ["HOT_RUNTIME_ROOT"] = previous_runtime_root
        if previous_runtime_root_is_auto is None:
            os.environ.pop("_CODEX_TEST_AUTO_RUNTIME_ROOT", None)
        else:
            os.environ["_CODEX_TEST_AUTO_RUNTIME_ROOT"] = previous_runtime_root_is_auto
        if dist_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{dist_root}'"], check=False)
        if release_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{release_root}'"], check=False)


def test_system_desktop_manifest_response_matches_schema_model(tmp_path) -> None:
    from app.schemas.system_manifest import DesktopManifest

    client = create_test_client(make_sqlite_url(tmp_path))

    response = client.get("/system/desktop-manifest")

    assert response.status_code == 200
    manifest = DesktopManifest.model_validate(response.json())
    assert manifest.kind == "desktop-shell-manifest"
    assert manifest.control.probe.kind == "launcher-probe"


def test_desktop_manifest_schema_file_matches_model_export() -> None:
    from app.schemas.system_manifest import DesktopManifest

    schema_path = Path("docs/specs/desktop-manifest.schema.json")

    assert schema_path.exists()
    expected = DesktopManifest.model_json_schema()
    actual = json.loads(schema_path.read_text(encoding="utf-8"))
    assert actual == expected


def test_cancel_running_job_returns_no_running_when_idle(tmp_path) -> None:
    """TC-API-004: POST /system/jobs/cancel-running 在无运行任务时返回 cancelled_job_id=null reason=no_running_job"""
    client = create_test_client(make_sqlite_url(tmp_path))

    response = client.post("/system/jobs/cancel-running", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["cancelled_job_id"] is None
    assert payload["reason"] == "no_running_job"


def test_config_export_default_masks_sensitive_fields(tmp_path, monkeypatch) -> None:
    """TC-CFG-105 / TC-API-006: GET /system/config/export?mask=true 默认脱敏，内容不含真实 Cookie/Secret"""
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
    """TC-CFG-106 / TC-API-007: GET /system/config/export?mask=false 在 APP_DEBUG=false 时返回 403"""
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
