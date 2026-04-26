from __future__ import annotations

from pathlib import Path

from app.runtime_paths import RuntimePaths, get_runtime_paths
from app.services.auth_state_service import AuthStateService


def test_get_runtime_paths_prefers_hot_runtime_root_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOT_RUNTIME_ROOT", str(tmp_path))

    paths = get_runtime_paths()
    auth_paths = AuthStateService(runtime_root=tmp_path).build_paths("bilibili")

    assert paths.runtime_root == tmp_path.resolve()
    assert paths.data_dir == tmp_path / "data"
    assert paths.logs_dir == tmp_path / "logs"
    assert paths.outputs_dir == tmp_path / "outputs"
    assert paths.reports_dir == tmp_path / "outputs" / "reports"
    assert paths.playwright_browsers_dir == tmp_path / "playwright-browsers"
    assert paths.bilibili_user_data_dir == auth_paths.user_data_dir
    assert paths.bilibili_storage_state_file == auth_paths.storage_state_file
    assert paths.env_file == tmp_path / "data" / "app.env"
    assert paths.pid_file == tmp_path / "data" / "launcher.pid"
    assert paths.launcher_log_file == tmp_path / "logs" / "launcher.log"


def test_runtime_paths_ensure_directories_creates_required_folders(tmp_path) -> None:
    paths = RuntimePaths(
        runtime_root=tmp_path,
        data_dir=tmp_path / "data",
        logs_dir=tmp_path / "logs",
        outputs_dir=tmp_path / "outputs",
        reports_dir=tmp_path / "outputs" / "reports",
        playwright_browsers_dir=tmp_path / "playwright-browsers",
        bilibili_user_data_dir=tmp_path / "data" / "bilibili-user-data",
        bilibili_storage_state_file=tmp_path / "data" / "bilibili-storage-state.json",
        env_file=tmp_path / "data" / "app.env",
        pid_file=tmp_path / "data" / "launcher.pid",
        launcher_log_file=tmp_path / "logs" / "launcher.log",
        app_log_file=tmp_path / "logs" / "app.log",
    )

    paths.ensure_directories()

    assert paths.data_dir.exists()
    assert paths.logs_dir.exists()
    assert paths.outputs_dir.exists()
    assert paths.reports_dir.exists()
    assert paths.playwright_browsers_dir.exists()
    assert paths.bilibili_user_data_dir.exists()
