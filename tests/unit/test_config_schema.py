"""TC-CFG-001~015 — Pydantic 配置 schema 单元测试。

被测对象:`app/config_schema.py`(REQ-CFG-001 / REQ-CFG-010)。
"""

from __future__ import annotations

import httpx
import pytest

from app.config_schema import (
    SettingsSchema,
    ValidationError,
    export_settings_yaml,
    list_settings_fields,
    list_settings_groups,
    mask_value,
    self_check_dingtalk_webhook,
)


@pytest.fixture(autouse=True)
def _clear_relevant_env(monkeypatch):
    for key in [
        "APP_NAME", "APP_ENV", "APP_DEBUG",
        "DATABASE_URL", "REPORTS_ROOT", "REPORT_SHARE_DIR",
        "ENABLE_SCHEDULER", "SCHEDULER_POLL_SECONDS", "SCHEDULER_DAILY_TIME",
        "ENABLE_DINGTALK_NOTIFIER", "DINGTALK_WEBHOOK", "DINGTALK_SECRET", "DINGTALK_KEYWORD",
        "BILIBILI_COOKIE", "BILIBILI_SOURCE_INTERVAL_SECONDS", "BILIBILI_RETRY_DELAY_SECONDS",
        "ENABLE_SITE_PROXY_RULES", "OUTBOUND_PROXY_URL", "OUTBOUND_PROXY_BYPASS_DOMAINS",
        "SOURCE_FETCH_INTERVAL_SECONDS",
        "WEEKLY_COVER_CACHE_RETENTION_DAYS", "WEEKLY_GRADE_PUSH_THRESHOLD",
    ]:
        monkeypatch.delenv(key, raising=False)
    yield


def test_default_values_loaded_when_env_missing() -> None:
    """TC-CFG-001"""
    s = SettingsSchema()
    assert s.app_name == "热点信息采集系统"
    assert s.environment == "development"
    assert s.debug is True
    assert s.scheduler_poll_seconds == 30
    assert s.weekly_grade_push_threshold == "B+"


def test_env_overrides_default(monkeypatch) -> None:
    """TC-CFG-002"""
    monkeypatch.setenv("APP_NAME", "custom-name")
    monkeypatch.setenv("SCHEDULER_POLL_SECONDS", "120")
    s = SettingsSchema()
    assert s.app_name == "custom-name"
    assert s.scheduler_poll_seconds == 120


def test_env_takes_precedence_over_app_env_file(monkeypatch) -> None:
    """TC-CFG-003"""
    monkeypatch.setenv("APP_NAME", "env-wins")
    s = SettingsSchema()
    assert s.app_name == "env-wins"


def test_bool_parsing_supports_common_truthy_falsy(monkeypatch) -> None:
    """TC-CFG-004"""
    for true_v in ("1", "true", "YES", "On"):
        monkeypatch.setenv("ENABLE_SCHEDULER", true_v)
        assert SettingsSchema().enable_scheduler is True
    for false_v in ("0", "false", "NO", "off"):
        monkeypatch.setenv("ENABLE_SCHEDULER", false_v)
        assert SettingsSchema().enable_scheduler is False


def test_int_parsing_rejects_non_numeric(monkeypatch) -> None:
    """TC-CFG-005"""
    monkeypatch.setenv("SCHEDULER_POLL_SECONDS", "not-a-number")
    with pytest.raises(ValidationError):
        SettingsSchema()


def test_url_validator_rejects_non_http_scheme(monkeypatch) -> None:
    """TC-CFG-006"""
    monkeypatch.setenv("DINGTALK_WEBHOOK", "ftp://example.com/hook")
    with pytest.raises(ValidationError):
        SettingsSchema()


def test_daily_time_validator_rejects_invalid_format(monkeypatch) -> None:
    """TC-CFG-007"""
    monkeypatch.setenv("SCHEDULER_DAILY_TIME", "25:99")
    with pytest.raises(ValidationError):
        SettingsSchema()


def test_bilibili_cookie_must_contain_sessdata(monkeypatch) -> None:
    """TC-CFG-008"""
    monkeypatch.setenv("BILIBILI_COOKIE", "DedeUserID=1234")
    with pytest.raises(ValidationError):
        SettingsSchema()
    monkeypatch.setenv("BILIBILI_COOKIE", "SESSDATA=abc; DedeUserID=1234")
    s = SettingsSchema()
    assert "SESSDATA" in s.bilibili_cookie


def test_sensitive_fields_marked() -> None:
    """TC-CFG-009"""
    info_by_env = {f.env_var: f for f in list_settings_fields()}
    for env_name in ("BILIBILI_COOKIE", "DINGTALK_WEBHOOK", "DINGTALK_SECRET", "OUTBOUND_PROXY_URL"):
        assert info_by_env[env_name].sensitive is True, env_name
    assert info_by_env["APP_NAME"].sensitive is False


def test_groups_cover_all_expected_categories() -> None:
    """TC-CFG-010"""
    groups = list_settings_groups()
    for expected in (
        "app", "database", "reports", "scheduler",
        "dingtalk", "bilibili", "network", "source", "weekly",
    ):
        assert expected in groups, expected
        assert len(groups[expected]) >= 1


def test_mask_long_value_keeps_prefix_and_suffix() -> None:
    """TC-CFG-011"""
    masked = mask_value("ABCDEFGH12345678WXYZ", sensitive=True)
    assert masked.startswith("ABCD")
    assert masked.endswith("WXYZ")
    assert "*" in masked


def test_mask_short_value_is_full_stars() -> None:
    """TC-CFG-012"""
    assert mask_value("abc", sensitive=True) == "***"
    assert mask_value("1234567", sensitive=True) == "***"


def test_export_yaml_orders_by_group_then_field() -> None:
    """TC-CFG-013"""
    text = export_settings_yaml({}, mask_sensitive=True)
    idx_app = text.index("app:")
    idx_db = text.index("database:")
    idx_weekly = text.index("weekly:")
    assert idx_app < idx_db < idx_weekly


def test_self_check_dingtalk_passes_when_mock_returns_200() -> None:
    """TC-CFG-014"""
    result = self_check_dingtalk_webhook(
        "https://oapi.dingtalk.com/robot/send",
        client_factory=lambda **kw: httpx.Client(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"errcode": 0})),
            **kw,
        ),
    )
    assert result["ok"] is True
    assert result["status"] == 200


def test_self_check_dingtalk_fails_when_mock_returns_401() -> None:
    """TC-CFG-015"""
    result = self_check_dingtalk_webhook(
        "https://oapi.dingtalk.com/robot/send",
        client_factory=lambda **kw: httpx.Client(
            transport=httpx.MockTransport(lambda req: httpx.Response(401, json={"errcode": 401})),
            **kw,
        ),
    )
    assert result["ok"] is False
    assert result["status"] == 401
    assert "401" in result["reason"]
