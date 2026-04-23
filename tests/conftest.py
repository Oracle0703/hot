import os
from pathlib import Path
from urllib.parse import urlparse

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
