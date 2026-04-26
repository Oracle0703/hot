from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RuntimePaths:
    runtime_root: Path
    data_dir: Path
    logs_dir: Path
    outputs_dir: Path
    reports_dir: Path
    playwright_browsers_dir: Path
    bilibili_user_data_dir: Path
    bilibili_storage_state_file: Path
    env_file: Path
    pid_file: Path
    launcher_log_file: Path
    app_log_file: Path

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.playwright_browsers_dir.mkdir(parents=True, exist_ok=True)
        self.bilibili_user_data_dir.mkdir(parents=True, exist_ok=True)


def detect_runtime_root(explicit_root: str | Path | None = None) -> Path:
    if explicit_root is not None:
        return Path(explicit_root).resolve()

    env_root = os.getenv("HOT_RUNTIME_ROOT")
    if env_root:
        return Path(env_root).resolve()

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[1]


def get_runtime_paths(explicit_root: str | Path | None = None) -> RuntimePaths:
    from app.services.auth_state_service import AuthStateService

    runtime_root = detect_runtime_root(explicit_root)
    data_dir = runtime_root / "data"
    logs_dir = runtime_root / "logs"
    outputs_dir = runtime_root / "outputs"
    reports_dir = outputs_dir / "reports"
    playwright_browsers_dir = runtime_root / "playwright-browsers"
    bilibili_auth_paths = AuthStateService(runtime_root=runtime_root).build_paths("bilibili")
    env_file = data_dir / "app.env"
    pid_file = data_dir / "launcher.pid"
    launcher_log_file = logs_dir / "launcher.log"
    app_log_file = logs_dir / "app.log"
    return RuntimePaths(
        runtime_root=runtime_root,
        data_dir=data_dir,
        logs_dir=logs_dir,
        outputs_dir=outputs_dir,
        reports_dir=reports_dir,
        playwright_browsers_dir=playwright_browsers_dir,
        bilibili_user_data_dir=bilibili_auth_paths.user_data_dir,
        bilibili_storage_state_file=bilibili_auth_paths.storage_state_file,
        env_file=env_file,
        pid_file=pid_file,
        launcher_log_file=launcher_log_file,
        app_log_file=app_log_file,
    )
