"""TC-SYS-101~103 — 日志轮转单元测试。"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

import pytest

from app.runtime_paths import get_runtime_paths
from app.services.log_setup import (
    APP_LOG_HANDLER_NAME,
    DEFAULT_BACKUP_COUNT,
    DEFAULT_MAX_BYTES,
    setup_app_logging,
)


@pytest.fixture(autouse=True)
def _isolate_root_logger():
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    yield
    # 还原
    for h in list(root.handlers):
        if getattr(h, "name", None) == APP_LOG_HANDLER_NAME:
            root.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass
    root.handlers[:] = saved
    root.setLevel(saved_level)


def _setup(tmp_path, monkeypatch, **kw):
    monkeypatch.setenv("HOT_RUNTIME_ROOT", str(tmp_path))
    paths = get_runtime_paths()
    return setup_app_logging(paths, **kw)


def test_rotating_handler_attached_with_expected_limits(tmp_path, monkeypatch):
    """TC-SYS-101"""
    handler = _setup(tmp_path, monkeypatch)
    assert isinstance(handler, logging.handlers.RotatingFileHandler)
    assert handler.maxBytes == DEFAULT_MAX_BYTES == 10 * 1024 * 1024
    assert handler.backupCount == DEFAULT_BACKUP_COUNT == 5
    # 幂等:再次调用返回同一 handler
    again = _setup(tmp_path, monkeypatch)
    assert again is handler


def test_app_log_rotates_when_threshold_exceeded(tmp_path, monkeypatch):
    """TC-SYS-102: 用极小阈值触发轮转,验证产生 .1 备份文件。"""
    handler = _setup(tmp_path, monkeypatch, max_bytes=512, backup_count=2)
    logger = logging.getLogger("test.rot.app")
    logger.setLevel(logging.INFO)
    payload = "x" * 200
    for _ in range(20):
        logger.info(payload)
    handler.flush()
    log_file = Path(handler.baseFilename)
    rotated = log_file.parent / (log_file.name + ".1")
    assert rotated.exists(), f"expected rotated file {rotated}"


def test_launcher_log_rotates_when_threshold_exceeded(tmp_path):
    """TC-SYS-103: launcher.setup_logging 已挂载 RotatingFileHandler,验证写入溢出生成 .1。"""
    from app.runtime_paths import RuntimePaths
    from launcher import setup_logging

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

    # 清掉同名 logger 旧 handler 以便重新安装小阈值
    existing = logging.getLogger("hot-launcher")
    for h in list(existing.handlers):
        existing.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    logger = setup_logging(paths)
    rfh = next((h for h in logger.handlers
                if isinstance(h, logging.handlers.RotatingFileHandler)), None)
    assert rfh is not None
    # 改小阈值再写
    rfh.maxBytes = 256
    payload = "x" * 200
    for _ in range(10):
        logger.info(payload)
    rfh.flush()
    rotated = Path(rfh.baseFilename).with_name(Path(rfh.baseFilename).name + ".1")
    assert rotated.exists()
