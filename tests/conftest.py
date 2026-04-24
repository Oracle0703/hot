import os
import threading
from pathlib import Path
from typing import Callable, Iterator
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

AUTO_RUNTIME_ROOT_ENV = "_CODEX_TEST_AUTO_RUNTIME_ROOT"


def create_test_client(database_url: str | None = None) -> TestClient:
    previous_database_url = os.environ.get("DATABASE_URL")
    has_database_override = database_url is not None
    if has_database_override:
        os.environ["DATABASE_URL"] = database_url
        runtime_root = _derive_runtime_root(database_url)
        current_runtime_root = os.environ.get("HOT_RUNTIME_ROOT")
        runtime_root_is_auto = os.environ.get(AUTO_RUNTIME_ROOT_ENV) == "1"
        if runtime_root is not None and (current_runtime_root is None or runtime_root_is_auto):
            os.environ["HOT_RUNTIME_ROOT"] = str(runtime_root)
            os.environ[AUTO_RUNTIME_ROOT_ENV] = "1"

    try:
        import app.models  # noqa: F401
        from app.db import get_engine
        from app.main import create_app
        from app.models.base import Base

        Base.metadata.create_all(bind=get_engine())
        client = TestClient(create_app(start_background_workers=False))
    finally:
        if has_database_override:
            if previous_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_database_url

    return client


def make_sqlite_url(tmp_path: Path, name: str = "test.db") -> str:
    return f"sqlite:///{(tmp_path / name).as_posix()}"


def _derive_runtime_root(database_url: str) -> Path | None:
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        return None
    raw_path = parsed.path
    if raw_path.startswith("/") and len(raw_path) >= 3 and raw_path[2] == ":":
        raw_path = raw_path[1:]
    database_path = Path(raw_path)
    if not database_path.is_absolute():
        return None
    return database_path.parent.resolve()


# ---- 公共夹具 (REQ-TEST-002) ---------------------------------------------------

@pytest.fixture()
def temp_app_env(tmp_path, monkeypatch) -> Iterator[Path]:
    """提供一个隔离的 app.env 工作目录,自动指向 tmp_path 并复位 get_settings 缓存。"""
    env_file = tmp_path / "app.env"
    monkeypatch.setenv("HOT_RUNTIME_ROOT", str(tmp_path))
    from app.config import get_settings
    get_settings.cache_clear()
    try:
        yield env_file
    finally:
        get_settings.cache_clear()


@pytest.fixture()
def cancel_event_factory() -> Callable[[], threading.Event]:
    """生成 ``threading.Event``,封装"测试需要的取消信号"语义,便于在自定义 source_executor 中阻塞。"""
    return threading.Event


@pytest.fixture()
def mock_strategy_registry(monkeypatch):
    """临时替换 ``CollectorRegistry`` 的工厂方法,测试可注入桩 collector / parser。

    用法::

        def test_xxx(mock_strategy_registry):
            mock_strategy_registry(get_collector=lambda src: FakeCollector())
    """
    from app.collectors.registry import CollectorRegistry

    def _patch(*, get_collector=None, get_parser=None):
        if get_collector is not None:
            monkeypatch.setattr(CollectorRegistry, "get_collector", lambda self, source: get_collector(source))
        if get_parser is not None:
            monkeypatch.setattr(CollectorRegistry, "get_parser", lambda self, source: get_parser(source))

    return _patch
