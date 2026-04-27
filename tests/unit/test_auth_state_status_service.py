from __future__ import annotations

from types import SimpleNamespace

from app.services.app_env_service import AppEnvService
from app.services.auth_state_service import AuthStateService
from app.services.auth_state_status_service import AuthStateStatusService


def test_auth_state_status_service_returns_ok_when_cookie_and_storage_state_exist(tmp_path) -> None:
    env_service = AppEnvService(env_file=tmp_path / "data" / "app.env")
    env_service.env_file.parent.mkdir(parents=True, exist_ok=True)
    env_service.env_file.write_text(
        "BILIBILI_COOKIE=SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123\n",
        encoding="utf-8",
    )
    auth_service = AuthStateService(runtime_root=tmp_path)
    auth_paths = auth_service.build_paths("bilibili")
    auth_paths.user_data_dir.mkdir(parents=True, exist_ok=True)
    auth_paths.storage_state_file.parent.mkdir(parents=True, exist_ok=True)
    auth_paths.storage_state_file.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")

    snapshot = AuthStateStatusService(
        app_env_service=env_service,
        auth_state_service=auth_service,
    ).build_snapshot()

    assert snapshot["status"] == "ok"
    assert snapshot["platforms"][0]["status"] == "ok"


def test_auth_state_status_service_returns_warning_when_cookie_exists_but_storage_state_missing(tmp_path) -> None:
    env_service = AppEnvService(env_file=tmp_path / "data" / "app.env")
    env_service.env_file.parent.mkdir(parents=True, exist_ok=True)
    env_service.env_file.write_text(
        "BILIBILI_COOKIE=SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123\n",
        encoding="utf-8",
    )
    auth_service = AuthStateService(runtime_root=tmp_path)

    snapshot = AuthStateStatusService(
        app_env_service=env_service,
        auth_state_service=auth_service,
    ).build_snapshot()

    assert snapshot["status"] == "warning"
    assert snapshot["platforms"][0]["status"] == "warning"
    assert any("storage state" in issue for issue in snapshot["platforms"][0]["issues"])


def test_auth_state_status_service_returns_error_for_invalid_storage_state_json(tmp_path) -> None:
    env_service = AppEnvService(env_file=tmp_path / "data" / "app.env")
    env_service.env_file.parent.mkdir(parents=True, exist_ok=True)
    env_service.env_file.write_text(
        "BILIBILI_COOKIE=SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123\n",
        encoding="utf-8",
    )
    auth_service = AuthStateService(runtime_root=tmp_path)
    auth_paths = auth_service.build_paths("bilibili")
    auth_paths.storage_state_file.parent.mkdir(parents=True, exist_ok=True)
    auth_paths.storage_state_file.write_text("{invalid-json", encoding="utf-8")

    snapshot = AuthStateStatusService(
        app_env_service=env_service,
        auth_state_service=auth_service,
    ).build_snapshot()

    assert snapshot["status"] == "error"
    assert snapshot["platforms"][0]["status"] == "error"


def test_auth_state_status_service_returns_bilibili_accounts_snapshot(tmp_path) -> None:
    env_service = AppEnvService(env_file=tmp_path / "data" / "app.env")
    env_service.env_file.parent.mkdir(parents=True, exist_ok=True)
    env_service.env_file.write_text(
        "\n".join(
            [
                "BILIBILI_COOKIE=SESSDATA=default-sess; bili_jct=default-jct; DedeUserID=1",
                "BILIBILI_COOKIE__CREATOR_A=SESSDATA=creator-sess; bili_jct=creator-jct; DedeUserID=2",
                "",
            ]
        ),
        encoding="utf-8",
    )
    auth_service = AuthStateService(runtime_root=tmp_path)
    default_paths = auth_service.build_paths("bilibili")
    creator_paths = auth_service.build_paths("bilibili", "creator-a")
    default_paths.user_data_dir.mkdir(parents=True, exist_ok=True)
    creator_paths.user_data_dir.mkdir(parents=True, exist_ok=True)
    default_paths.storage_state_file.parent.mkdir(parents=True, exist_ok=True)
    default_paths.storage_state_file.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
    creator_paths.storage_state_file.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")

    snapshot = AuthStateStatusService(
        app_env_service=env_service,
        auth_state_service=auth_service,
        site_accounts_provider=lambda: [
            SimpleNamespace(platform="bilibili", account_key="default", display_name="默认账号", enabled=True, is_default=True),
            SimpleNamespace(platform="bilibili", account_key="creator-a", display_name="账号A", enabled=True, is_default=False),
        ],
    ).build_snapshot()

    bilibili = snapshot["platforms"][0]
    assert bilibili["status"] == "ok"
    assert [account["account_key"] for account in bilibili["accounts"]] == ["default", "creator-a"]
    assert bilibili["accounts"][0]["is_default"] is True
    assert bilibili["accounts"][1]["display_name"] == "账号A"
