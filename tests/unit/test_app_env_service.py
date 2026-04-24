from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.services.app_env_service import AppEnvService


def test_app_env_service_updates_dingtalk_settings_and_writes_env_file(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / 'data' / 'app.env'
    monkeypatch.delenv('ENABLE_DINGTALK_NOTIFIER', raising=False)
    monkeypatch.delenv('DINGTALK_WEBHOOK', raising=False)
    monkeypatch.delenv('DINGTALK_SECRET', raising=False)
    monkeypatch.delenv('DINGTALK_KEYWORD', raising=False)

    service = AppEnvService(env_file=env_file)
    settings = service.update_dingtalk_settings(
        enabled=True,
        webhook='https://oapi.dingtalk.com/robot/send?access_token=test-token',
        secret='SECdemo',
        keyword='热点报告',
    )

    assert settings.enabled is True
    assert settings.webhook.endswith('access_token=test-token')
    assert settings.secret == 'SECdemo'
    assert settings.keyword == '热点报告'
    assert env_file.exists()
    assert 'ENABLE_DINGTALK_NOTIFIER=true' in env_file.read_text(encoding='utf-8')
    assert os.environ['DINGTALK_WEBHOOK'].endswith('access_token=test-token')


def test_app_env_service_reads_bom_prefixed_env_file(tmp_path, monkeypatch) -> None:
    """TC-CFG-101: 已存在的 app.env 能被读取并返回持久化值"""
    env_file = tmp_path / 'data' / 'app.env'
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        'ENABLE_DINGTALK_NOTIFIER=true\n'
        'DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=test-token\n'
        'DINGTALK_SECRET=SECdemo\n'
        'DINGTALK_KEYWORD=热点报告\n',
        encoding='utf-8-sig',
    )
    monkeypatch.delenv('ENABLE_DINGTALK_NOTIFIER', raising=False)
    monkeypatch.delenv('DINGTALK_WEBHOOK', raising=False)
    monkeypatch.delenv('DINGTALK_SECRET', raising=False)
    monkeypatch.delenv('DINGTALK_KEYWORD', raising=False)

    settings = AppEnvService(env_file=env_file).get_dingtalk_settings()

    assert settings.enabled is True
    assert settings.webhook.endswith('access_token=test-token')
    assert settings.secret == 'SECdemo'
    assert settings.keyword == '热点报告'

def test_app_env_service_updates_site_proxy_settings_and_writes_env_file(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / 'data' / 'app.env'
    monkeypatch.delenv('ENABLE_SITE_PROXY_RULES', raising=False)
    monkeypatch.delenv('OUTBOUND_PROXY_URL', raising=False)
    monkeypatch.delenv('OUTBOUND_PROXY_BYPASS_DOMAINS', raising=False)

    service = AppEnvService(env_file=env_file)
    settings = service.update_network_settings(
        enabled=True,
        outbound_proxy_url='http://127.0.0.1:7890',
        bypass_domains='bilibili.com,hdslb.com,bilivideo.com',
    )

    assert settings.enabled is True
    assert settings.outbound_proxy_url == 'http://127.0.0.1:7890'
    assert settings.bypass_domains == 'bilibili.com,hdslb.com,bilivideo.com'
    assert 'ENABLE_SITE_PROXY_RULES=true' in env_file.read_text(encoding='utf-8')
    assert os.environ['OUTBOUND_PROXY_URL'] == 'http://127.0.0.1:7890'


def test_app_env_service_reads_site_proxy_settings_from_env_file(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / 'data' / 'app.env'
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        'ENABLE_SITE_PROXY_RULES=true\n'
        'OUTBOUND_PROXY_URL=http://127.0.0.1:7890\n'
        'OUTBOUND_PROXY_BYPASS_DOMAINS=bilibili.com,hdslb.com,bilivideo.com\n',
        encoding='utf-8-sig',
    )
    monkeypatch.delenv('ENABLE_SITE_PROXY_RULES', raising=False)
    monkeypatch.delenv('OUTBOUND_PROXY_URL', raising=False)
    monkeypatch.delenv('OUTBOUND_PROXY_BYPASS_DOMAINS', raising=False)

    settings = AppEnvService(env_file=env_file).get_network_settings()

    assert settings.enabled is True
    assert settings.outbound_proxy_url == 'http://127.0.0.1:7890'
    assert settings.bypass_domains == 'bilibili.com,hdslb.com,bilivideo.com'

def test_app_env_service_updates_bilibili_cookie_and_writes_env_file(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / 'data' / 'app.env'
    monkeypatch.delenv('BILIBILI_COOKIE', raising=False)

    service = AppEnvService(env_file=env_file)
    settings = service.update_bilibili_settings(
        cookie='SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123'
    )

    assert settings.cookie == 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123'
    assert env_file.exists()
    assert 'BILIBILI_COOKIE=SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123' in env_file.read_text(encoding='utf-8')
    assert os.environ['BILIBILI_COOKIE'] == 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123'


def test_app_env_service_reads_bilibili_cookie_from_env_file(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / 'data' / 'app.env'
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        'BILIBILI_COOKIE=SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123\n',
        encoding='utf-8-sig',
    )
    monkeypatch.delenv('BILIBILI_COOKIE', raising=False)

    settings = AppEnvService(env_file=env_file).get_bilibili_settings()

    assert settings.cookie == 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123'


def test_app_env_service_normalizes_prefixed_bilibili_cookie(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / 'data' / 'app.env'
    monkeypatch.delenv('BILIBILI_COOKIE', raising=False)

    settings = AppEnvService(env_file=env_file).update_bilibili_settings(
        cookie='BILIBILI_COOKIE=SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123'
    )

    assert settings.cookie == 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123'


def test_app_env_service_normalizes_quoted_multiline_bilibili_cookie(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / 'data' / 'app.env'
    monkeypatch.delenv('BILIBILI_COOKIE', raising=False)

    settings = AppEnvService(env_file=env_file).update_bilibili_settings(
        cookie='"  SESSDATA=test-sess;\n bili_jct=test-jct;\n DedeUserID=123  "'
    )

    assert settings.cookie == 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123'


def test_app_env_service_rejects_bilibili_cookie_without_sessdata(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / 'data' / 'app.env'
    monkeypatch.delenv('BILIBILI_COOKIE', raising=False)

    service = AppEnvService(env_file=env_file)

    with pytest.raises(ValueError, match='SESSDATA'):
        service.update_bilibili_settings(cookie='bili_jct=test-jct; DedeUserID=123')


def test_app_env_service_rejects_empty_bilibili_cookie(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / 'data' / 'app.env'
    monkeypatch.delenv('BILIBILI_COOKIE', raising=False)

    service = AppEnvService(env_file=env_file)

    with pytest.raises(ValueError, match='不能为空'):
        service.update_bilibili_settings(cookie='   ')


def test_app_env_service_updates_fetch_interval_settings_and_writes_env_file(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / 'data' / 'app.env'
    monkeypatch.delenv('SOURCE_FETCH_INTERVAL_SECONDS', raising=False)
    monkeypatch.delenv('BILIBILI_SOURCE_INTERVAL_SECONDS', raising=False)
    monkeypatch.delenv('BILIBILI_RETRY_DELAY_SECONDS', raising=False)

    service = AppEnvService(env_file=env_file)
    settings = service.update_fetch_interval_settings(
        source_fetch_interval_seconds=3,
        bilibili_source_interval_seconds=12,
        bilibili_retry_delay_seconds=7,
    )

    assert settings.source_fetch_interval_seconds == 3
    assert settings.bilibili_source_interval_seconds == 12
    assert settings.bilibili_retry_delay_seconds == 7
    assert 'SOURCE_FETCH_INTERVAL_SECONDS=3' in env_file.read_text(encoding='utf-8')
    assert 'BILIBILI_SOURCE_INTERVAL_SECONDS=12' in env_file.read_text(encoding='utf-8')
    assert 'BILIBILI_RETRY_DELAY_SECONDS=7' in env_file.read_text(encoding='utf-8')
    assert os.environ['SOURCE_FETCH_INTERVAL_SECONDS'] == '3'
    assert os.environ['BILIBILI_SOURCE_INTERVAL_SECONDS'] == '12'
    assert os.environ['BILIBILI_RETRY_DELAY_SECONDS'] == '7'


def test_app_env_service_reads_fetch_interval_settings_from_env_file(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / 'data' / 'app.env'
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        'SOURCE_FETCH_INTERVAL_SECONDS=5\n'
        'BILIBILI_SOURCE_INTERVAL_SECONDS=15\n'
        'BILIBILI_RETRY_DELAY_SECONDS=9\n',
        encoding='utf-8-sig',
    )
    monkeypatch.delenv('SOURCE_FETCH_INTERVAL_SECONDS', raising=False)
    monkeypatch.delenv('BILIBILI_SOURCE_INTERVAL_SECONDS', raising=False)
    monkeypatch.delenv('BILIBILI_RETRY_DELAY_SECONDS', raising=False)

    settings = AppEnvService(env_file=env_file).get_fetch_interval_settings()

    assert settings.source_fetch_interval_seconds == 5
    assert settings.bilibili_source_interval_seconds == 15
    assert settings.bilibili_retry_delay_seconds == 9


def test_app_env_service_concurrent_writes_do_not_corrupt_file(tmp_path, monkeypatch) -> None:
    """TC-CFG-102: 多线程并发 update_dingtalk_settings 不会因竞争丢字段或截断文件"""
    import threading

    env_file = tmp_path / 'data' / 'app.env'
    monkeypatch.delenv('DINGTALK_WEBHOOK', raising=False)

    errors: list[BaseException] = []

    def write(label: str) -> None:
        try:
            AppEnvService(env_file=env_file).update_dingtalk_settings(
                enabled=True,
                webhook=f'https://example.com/{label}',
                secret=f'SEC{label}',
                keyword=label,
            )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(f't{i}',)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert not errors, f'concurrent writes raised: {errors}'
    text = env_file.read_text(encoding='utf-8')
    # 文件至少含期望的 key,且最终值是某次 write 的内容
    assert 'ENABLE_DINGTALK_NOTIFIER=true' in text
    assert 'DINGTALK_WEBHOOK=https://example.com/t' in text
    assert 'DINGTALK_KEYWORD=t' in text
    # 不存在残留的 .tmp
    leftover = list(env_file.parent.glob('app.env.*.tmp'))
    assert leftover == []


def test_app_env_service_keeps_original_file_when_atomic_replace_fails(tmp_path, monkeypatch) -> None:
    """TC-CFG-103: os.replace 失败时主文件保持原值且无残留临时文件"""
    env_file = tmp_path / 'data' / 'app.env'
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text('DINGTALK_KEYWORD=old-value\n', encoding='utf-8')

    def fail_replace(src: str, dst: Path) -> None:
        raise OSError('replace failed')

    monkeypatch.setattr('app.services.app_env_service.os.replace', fail_replace)

    with pytest.raises(OSError, match='replace failed'):
        AppEnvService(env_file=env_file).update_dingtalk_settings(
            enabled=True,
            webhook='https://example.com/hook',
            secret='SECdemo',
            keyword='new-value',
        )

    assert env_file.read_text(encoding='utf-8') == 'DINGTALK_KEYWORD=old-value\n'
    assert list(env_file.parent.glob('app.env.*.tmp')) == []


def test_app_env_service_ensure_env_file_creates_managed_placeholders(tmp_path) -> None:
    """TC-CFG-104: ensure_env_file 在文件不存在时生成受管 key 占位内容"""
    env_file = tmp_path / 'data' / 'app.env'

    created = AppEnvService(env_file=env_file).ensure_env_file()

    assert created == env_file
    text = env_file.read_text(encoding='utf-8')
    assert 'DINGTALK_WEBHOOK=' in text
    assert 'BILIBILI_COOKIE=' in text
    assert 'BILIBILI_RETRY_DELAY_SECONDS=' in text
