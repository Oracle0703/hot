from pathlib import Path

from app.db import create_session_factory, get_engine


def test_get_engine_uses_sqlite_driver_for_default_url(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "hot_topics.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")

    engine = get_engine()

    assert engine.url.drivername == "sqlite"
    assert Path(engine.url.database).name == "hot_topics.db"


def test_create_session_factory_binds_engine(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "session.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")

    session_factory = create_session_factory()

    with session_factory() as session:
        assert session.bind is not None
        assert session.bind.url.drivername == "sqlite"
