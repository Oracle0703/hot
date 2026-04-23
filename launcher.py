from __future__ import annotations

import argparse
import atexit
import logging
import os
import socket
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from app.main import create_app
from app.runtime_paths import RuntimePaths, get_runtime_paths


KNOWN_APP_ENV_KEYS = {
    "APP_NAME",
    "APP_ENV",
    "APP_DEBUG",
    "DATABASE_URL",
    "REPORTS_ROOT",
    "ENABLE_SCHEDULER",
    "SCHEDULER_POLL_SECONDS",
    "PLAYWRIGHT_BROWSERS_PATH",
    "ENABLE_DINGTALK_NOTIFIER",
    "DINGTALK_WEBHOOK",
    "DINGTALK_SECRET",
    "DINGTALK_KEYWORD",
}


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _resolve_sqlite_url(paths: RuntimePaths, value: str) -> str:
    prefix = "sqlite:///"
    if not value.startswith(prefix):
        return value

    raw_path = value.removeprefix(prefix)
    if not raw_path:
        return value

    candidate = Path(raw_path)
    if not candidate.is_absolute():
        normalized = raw_path.removeprefix("./").removeprefix(".\\")
        candidate = paths.runtime_root / normalized
    return f"sqlite:///{candidate.resolve().as_posix()}"


def _resolve_path_value(paths: RuntimePaths, value: str) -> str:
    candidate = Path(value)
    if candidate.is_absolute():
        return str(candidate)
    return str((paths.runtime_root / candidate).resolve())


def _resolve_env_value(paths: RuntimePaths, key: str, value: str) -> str:
    if key == "DATABASE_URL":
        return _resolve_sqlite_url(paths, value)
    if key in {"REPORTS_ROOT", "PLAYWRIGHT_BROWSERS_PATH"}:
        return _resolve_path_value(paths, value)
    return value


def build_runtime_environment(
    paths: RuntimePaths,
    file_values: dict[str, str],
    process_env: dict[str, str] | None = None,
) -> dict[str, str]:
    if process_env is None:
        process_env = dict(os.environ)

    values: dict[str, str] = {
        "HOT_RUNTIME_ROOT": str(paths.runtime_root),
        "DATABASE_URL": f"sqlite:///{(paths.data_dir / 'hot_topics.db').as_posix()}",
        "REPORTS_ROOT": str(paths.reports_dir),
        "PLAYWRIGHT_BROWSERS_PATH": str(paths.playwright_browsers_dir),
    }

    for key, value in file_values.items():
        values[key] = _resolve_env_value(paths, key, value)

    for key in KNOWN_APP_ENV_KEYS.union(file_values.keys()):
        if key in process_env:
            values[key] = _resolve_env_value(paths, key, process_env[key])

    values["HOT_RUNTIME_ROOT"] = str(paths.runtime_root)
    return values


def build_browser_url(bind_host: str, port: int) -> str:
    browser_host = "127.0.0.1" if bind_host in {"0.0.0.0", "::"} else bind_host
    return f"http://{browser_host}:{port}/"


def is_port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_port(host: str, port: int, timeout_seconds: float = 15.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if is_port_open(host, port):
            return True
        time.sleep(0.1)
    return False


def setup_logging(paths: RuntimePaths) -> logging.Logger:
    logger = logging.getLogger("hot-launcher")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(paths.launcher_log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _write_pid_file(paths: RuntimePaths) -> None:
    paths.pid_file.write_text(str(os.getpid()), encoding="utf-8")


def _cleanup_pid_file(paths: RuntimePaths) -> None:
    if paths.pid_file.exists():
        paths.pid_file.unlink()


def _open_browser_when_ready(bind_host: str, port: int, logger: logging.Logger) -> None:
    url = build_browser_url(bind_host, port)
    if wait_for_port("127.0.0.1" if bind_host == "0.0.0.0" else bind_host, port):
        webbrowser.open(url)
        logger.info("browser opened: %s", url)
    else:
        logger.error("server did not become ready in time: %s", url)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="热点采集系统启动器")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=38080)
    parser.add_argument("--runtime-root", default=None)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = get_runtime_paths(args.runtime_root)
    paths.ensure_directories()
    runtime_env = build_runtime_environment(paths, load_env_file(paths.env_file), dict(os.environ))
    os.environ.update(runtime_env)

    browser_url = build_browser_url(args.host, args.port)
    if args.dry_run:
        print(f"runtime_root={paths.runtime_root}")
        print(f"url={browser_url}")
        print(f"database={runtime_env['DATABASE_URL']}")
        print(f"reports={runtime_env['REPORTS_ROOT']}")
        print(f"playwright={runtime_env['PLAYWRIGHT_BROWSERS_PATH']}")
        return 0

    logger = setup_logging(paths)
    logger.info("launcher starting")
    logger.info("runtime root: %s", paths.runtime_root)
    logger.info("database: %s", runtime_env["DATABASE_URL"])
    logger.info("reports root: %s", runtime_env["REPORTS_ROOT"])

    target_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    if is_port_open(target_host, args.port):
        logger.info("server already running, opening browser only")
        if not args.no_browser:
            webbrowser.open(browser_url)
        return 0

    _write_pid_file(paths)
    atexit.register(_cleanup_pid_file, paths)

    if not args.no_browser:
        threading.Thread(
            target=_open_browser_when_ready,
            args=(args.host, args.port, logger),
            daemon=True,
        ).start()

    config = uvicorn.Config(
        app=create_app(start_background_workers=True),
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info",
    )
    server = uvicorn.Server(config)
    try:
        server.run()
        return 0
    except Exception:
        logger.exception("launcher crashed")
        raise
    finally:
        _cleanup_pid_file(paths)


if __name__ == "__main__":
    raise SystemExit(main())

