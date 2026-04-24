from __future__ import annotations

import os

from app.config import get_settings


def test_get_settings_reads_bom_prefixed_runtime_env_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    monkeypatch.delenv('ENABLE_DINGTALK_NOTIFIER', raising=False)
    monkeypatch.delenv('DINGTALK_WEBHOOK', raising=False)
    monkeypatch.delenv('DINGTALK_SECRET', raising=False)
    monkeypatch.delenv('DINGTALK_KEYWORD', raising=False)

    env_file = tmp_path / 'data' / 'app.env'
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        'ENABLE_DINGTALK_NOTIFIER=true\n'
        'DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=test-token\n'
        'DINGTALK_SECRET=SECdemo\n'
        'DINGTALK_KEYWORD=热点报告\n',
        encoding='utf-8-sig',
    )

    settings = get_settings()

    assert settings.enable_dingtalk_notifier is True
    assert settings.dingtalk_webhook.endswith('access_token=test-token')
    assert settings.dingtalk_secret == 'SECdemo'
    assert settings.dingtalk_keyword == '热点报告'


def test_get_settings_hydrates_non_settings_runtime_env_keys(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    monkeypatch.delenv('X_AUTH_TOKEN', raising=False)
    monkeypatch.delenv('X_CT0', raising=False)

    env_file = tmp_path / 'data' / 'app.env'
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        'X_AUTH_TOKEN=test-auth\n'
        'X_CT0=test-ct0\n',
        encoding='utf-8-sig',
    )

    get_settings()

    assert os.environ['X_AUTH_TOKEN'] == 'test-auth'
    assert os.environ['X_CT0'] == 'test-ct0'


def test_get_settings_reads_bilibili_cookie_from_runtime_env_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    monkeypatch.delenv('BILIBILI_COOKIE', raising=False)

    env_file = tmp_path / 'data' / 'app.env'
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        'BILIBILI_COOKIE=SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123\n',
        encoding='utf-8-sig',
    )

    settings = get_settings()

    assert settings.bilibili_cookie.startswith('SESSDATA=test-sess')


def test_get_settings_reads_site_proxy_rule_values_from_runtime_env_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    monkeypatch.delenv('ENABLE_SITE_PROXY_RULES', raising=False)
    monkeypatch.delenv('OUTBOUND_PROXY_URL', raising=False)
    monkeypatch.delenv('OUTBOUND_PROXY_BYPASS_DOMAINS', raising=False)

    env_file = tmp_path / 'data' / 'app.env'
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        'ENABLE_SITE_PROXY_RULES=true\n'
        'OUTBOUND_PROXY_URL=http://127.0.0.1:7890\n'
        'OUTBOUND_PROXY_BYPASS_DOMAINS=bilibili.com,hdslb.com,bilivideo.com\n',
        encoding='utf-8-sig',
    )

    settings = get_settings()

    assert settings.enable_site_proxy_rules is True
    assert settings.outbound_proxy_url == 'http://127.0.0.1:7890'
    assert settings.outbound_proxy_bypass_domains == 'bilibili.com,hdslb.com,bilivideo.com'


def test_get_settings_reads_source_fetch_interval_values_from_runtime_env_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    monkeypatch.delenv('SOURCE_FETCH_INTERVAL_SECONDS', raising=False)
    monkeypatch.delenv('BILIBILI_SOURCE_INTERVAL_SECONDS', raising=False)
    monkeypatch.delenv('BILIBILI_RETRY_DELAY_SECONDS', raising=False)

    env_file = tmp_path / 'data' / 'app.env'
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        'SOURCE_FETCH_INTERVAL_SECONDS=3\n'
        'BILIBILI_SOURCE_INTERVAL_SECONDS=12\n'
        'BILIBILI_RETRY_DELAY_SECONDS=7\n',
        encoding='utf-8-sig',
    )

    settings = get_settings()

    assert settings.source_fetch_interval_seconds == 3
    assert settings.bilibili_source_interval_seconds == 12
    assert settings.bilibili_retry_delay_seconds == 7


def test_get_settings_reads_weekly_cover_cache_retention_days_from_runtime_env_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    monkeypatch.delenv('WEEKLY_COVER_CACHE_RETENTION_DAYS', raising=False)

    env_file = tmp_path / 'data' / 'app.env'
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        'WEEKLY_COVER_CACHE_RETENTION_DAYS=45\n',
        encoding='utf-8-sig',
    )

    settings = get_settings()

    assert settings.weekly_cover_cache_retention_days == 45


def test_get_settings_reads_weekly_grade_push_threshold_from_runtime_env_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    monkeypatch.delenv('WEEKLY_GRADE_PUSH_THRESHOLD', raising=False)

    env_file = tmp_path / 'data' / 'app.env'
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        'WEEKLY_GRADE_PUSH_THRESHOLD=A\n',
        encoding='utf-8-sig',
    )

    settings = get_settings()

    assert settings.weekly_grade_push_threshold == 'A'
