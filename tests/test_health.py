from app.db import get_database_config
from app.config import get_settings
from app.runtime_paths import get_runtime_paths
from tests.conftest import create_test_client
from tests.conftest import make_sqlite_url


def test_health_endpoint_returns_ok_status() -> None:
    client = create_test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_settings_returns_string_defaults() -> None:
    settings = get_settings()

    assert settings.app_name == "热点信息采集系统"
    assert settings.environment == "development"
    assert settings.database_url == "sqlite:///./data/hot_topics.db"


def test_database_config_uses_mysql_url_when_env_is_set(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://hot_user:secret@127.0.0.1:3306/hot_topic")

    database_config = get_database_config()

    assert database_config.url == "mysql+pymysql://hot_user:secret@127.0.0.1:3306/hot_topic"
    assert database_config.driver == "mysql"


def test_database_config_defaults_to_sqlite(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    database_config = get_database_config()

    assert database_config.url == "sqlite:///./data/hot_topics.db"
    assert database_config.driver == "sqlite"


def test_create_test_client_isolates_runtime_root_when_database_is_overridden(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("HOT_RUNTIME_ROOT", raising=False)

    client = create_test_client(make_sqlite_url(tmp_path, "health-isolation.db"))
    response = client.get("/scheduler")

    assert response.status_code == 200
    assert str(get_runtime_paths(tmp_path).env_file) in response.text
