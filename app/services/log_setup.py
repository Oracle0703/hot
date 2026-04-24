"""阶段 1.4 完结篇 — 应用层日志轮转(REQ-SYS-101~103)。

提供 ``setup_app_logging(paths)``,把 RotatingFileHandler 安装到 root logger,
并保证幂等(多次调用不会重复挂载)。
"""
from __future__ import annotations

import logging
import logging.handlers

from app.runtime_paths import RuntimePaths

DEFAULT_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 5
APP_LOG_HANDLER_NAME = "hot-app-rotating"


def setup_app_logging(
    paths: RuntimePaths,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    level: int = logging.INFO,
) -> logging.Handler:
    """安装 RotatingFileHandler 到 root logger。返回已安装的 handler。

    幂等:重复调用时复用同名 handler。
    """
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    for h in root.handlers:
        if getattr(h, "name", None) == APP_LOG_HANDLER_NAME:
            return h
    handler = logging.handlers.RotatingFileHandler(
        paths.app_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.set_name(APP_LOG_HANDLER_NAME)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    handler.setLevel(level)
    root.addHandler(handler)
    if root.level > level or root.level == logging.NOTSET:
        root.setLevel(level)
    return handler


__all__ = ["setup_app_logging", "DEFAULT_MAX_BYTES", "DEFAULT_BACKUP_COUNT", "APP_LOG_HANDLER_NAME"]
