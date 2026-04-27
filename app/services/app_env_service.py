from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import portalocker

from app.config import get_settings
from app.runtime_paths import get_runtime_paths
from app.services import config_encryption

MANAGED_KEYS = (
    'ENABLE_DINGTALK_NOTIFIER',
    'DINGTALK_WEBHOOK',
    'DINGTALK_SECRET',
    'DINGTALK_KEYWORD',
    'BILIBILI_COOKIE',
    'ENABLE_SITE_PROXY_RULES',
    'OUTBOUND_PROXY_URL',
    'OUTBOUND_PROXY_BYPASS_DOMAINS',
    'SOURCE_FETCH_INTERVAL_SECONDS',
    'BILIBILI_SOURCE_INTERVAL_SECONDS',
    'BILIBILI_RETRY_DELAY_SECONDS',
)
# REQ-SEC-001: 这些字段在 CONFIG_ENCRYPTION_KEY 启用时会被 Fernet 加密,
# 带 ``enc:`` 前缀落盘;未启用时透传明文并走一次 warning。
SENSITIVE_KEYS = (
    'BILIBILI_COOKIE',
    'DINGTALK_WEBHOOK',
    'DINGTALK_SECRET',
    'OUTBOUND_PROXY_URL',
)
_ENC_PREFIX = 'enc:'
ENV_OUTPUT_ORDER = (
    'APP_NAME',
    'APP_ENV',
    'APP_DEBUG',
    'DATABASE_URL',
    'REPORTS_ROOT',
    'ENABLE_SCHEDULER',
    'SCHEDULER_POLL_SECONDS',
    'ENABLE_DINGTALK_NOTIFIER',
    'DINGTALK_WEBHOOK',
    'DINGTALK_SECRET',
    'DINGTALK_KEYWORD',
    'BILIBILI_COOKIE',
    'ENABLE_SITE_PROXY_RULES',
    'OUTBOUND_PROXY_URL',
    'OUTBOUND_PROXY_BYPASS_DOMAINS',
    'SOURCE_FETCH_INTERVAL_SECONDS',
    'BILIBILI_SOURCE_INTERVAL_SECONDS',
    'BILIBILI_RETRY_DELAY_SECONDS',
)


@dataclass(slots=True)
class DingTalkEnvSettings:
    enabled: bool
    webhook: str
    secret: str
    keyword: str
    env_file: Path


@dataclass(slots=True)
class BilibiliEnvSettings:
    account_key: str
    cookie: str
    env_file: Path


@dataclass(slots=True)
class NetworkEnvSettings:
    enabled: bool
    outbound_proxy_url: str
    bypass_domains: str
    env_file: Path


@dataclass(slots=True)
class FetchIntervalEnvSettings:
    source_fetch_interval_seconds: int
    bilibili_source_interval_seconds: int
    bilibili_retry_delay_seconds: int
    env_file: Path


class AppEnvService:
    def __init__(self, env_file: Path | None = None) -> None:
        self.env_file = env_file or get_runtime_paths().env_file

    def get_dingtalk_settings(self) -> DingTalkEnvSettings:
        values = self._load_values()
        settings = get_settings()
        return DingTalkEnvSettings(
            enabled=self._get_bool(values.get('ENABLE_DINGTALK_NOTIFIER'), settings.enable_dingtalk_notifier),
            webhook=values.get('DINGTALK_WEBHOOK', settings.dingtalk_webhook),
            secret=values.get('DINGTALK_SECRET', settings.dingtalk_secret),
            keyword=values.get('DINGTALK_KEYWORD', settings.dingtalk_keyword),
            env_file=self.env_file,
        )

    def update_dingtalk_settings(self, enabled: bool, webhook: str, secret: str, keyword: str) -> DingTalkEnvSettings:
        values = self._load_values()
        values['ENABLE_DINGTALK_NOTIFIER'] = 'true' if enabled else 'false'
        values['DINGTALK_WEBHOOK'] = webhook.strip()
        values['DINGTALK_SECRET'] = secret.strip()
        values['DINGTALK_KEYWORD'] = keyword.strip()
        self._write_values(values)

        os.environ['ENABLE_DINGTALK_NOTIFIER'] = values['ENABLE_DINGTALK_NOTIFIER']
        os.environ['DINGTALK_WEBHOOK'] = values['DINGTALK_WEBHOOK']
        os.environ['DINGTALK_SECRET'] = values['DINGTALK_SECRET']
        os.environ['DINGTALK_KEYWORD'] = values['DINGTALK_KEYWORD']
        return self.get_dingtalk_settings()

    def get_bilibili_settings(self, account_key: str = 'default') -> BilibiliEnvSettings:
        values = self._load_values()
        settings = get_settings()
        env_key = self._bilibili_cookie_env_key(account_key)
        fallback_cookie = settings.bilibili_cookie if env_key == 'BILIBILI_COOKIE' else ''
        return BilibiliEnvSettings(
            account_key=self._normalize_account_key(account_key),
            cookie=values.get(env_key, fallback_cookie),
            env_file=self.env_file,
        )

    def update_bilibili_settings(self, cookie: str, account_key: str = 'default') -> BilibiliEnvSettings:
        values = self._load_values()
        env_key = self._bilibili_cookie_env_key(account_key)
        values[env_key] = self._normalize_bilibili_cookie(cookie)
        self._write_values(values)

        os.environ[env_key] = values[env_key]
        if env_key == 'BILIBILI_COOKIE':
            os.environ['BILIBILI_COOKIE'] = values[env_key]
        return self.get_bilibili_settings(account_key=account_key)

    def get_network_settings(self) -> NetworkEnvSettings:
        values = self._load_values()
        settings = get_settings()
        return NetworkEnvSettings(
            enabled=self._get_bool(values.get('ENABLE_SITE_PROXY_RULES'), settings.enable_site_proxy_rules),
            outbound_proxy_url=values.get('OUTBOUND_PROXY_URL', settings.outbound_proxy_url),
            bypass_domains=values.get('OUTBOUND_PROXY_BYPASS_DOMAINS', settings.outbound_proxy_bypass_domains),
            env_file=self.env_file,
        )

    def update_network_settings(self, enabled: bool, outbound_proxy_url: str, bypass_domains: str) -> NetworkEnvSettings:
        values = self._load_values()
        values['ENABLE_SITE_PROXY_RULES'] = 'true' if enabled else 'false'
        values['OUTBOUND_PROXY_URL'] = outbound_proxy_url.strip()
        values['OUTBOUND_PROXY_BYPASS_DOMAINS'] = bypass_domains.strip()
        self._write_values(values)

        os.environ['ENABLE_SITE_PROXY_RULES'] = values['ENABLE_SITE_PROXY_RULES']
        os.environ['OUTBOUND_PROXY_URL'] = values['OUTBOUND_PROXY_URL']
        os.environ['OUTBOUND_PROXY_BYPASS_DOMAINS'] = values['OUTBOUND_PROXY_BYPASS_DOMAINS']
        return self.get_network_settings()

    def get_fetch_interval_settings(self) -> FetchIntervalEnvSettings:
        values = self._load_values()
        settings = get_settings()
        return FetchIntervalEnvSettings(
            source_fetch_interval_seconds=self._get_int(
                values.get('SOURCE_FETCH_INTERVAL_SECONDS'),
                settings.source_fetch_interval_seconds,
            ),
            bilibili_source_interval_seconds=self._get_int(
                values.get('BILIBILI_SOURCE_INTERVAL_SECONDS'),
                settings.bilibili_source_interval_seconds,
            ),
            bilibili_retry_delay_seconds=self._get_int(
                values.get('BILIBILI_RETRY_DELAY_SECONDS'),
                settings.bilibili_retry_delay_seconds,
            ),
            env_file=self.env_file,
        )

    def update_fetch_interval_settings(
        self,
        source_fetch_interval_seconds: int,
        bilibili_source_interval_seconds: int,
        bilibili_retry_delay_seconds: int,
    ) -> FetchIntervalEnvSettings:
        values = self._load_values()
        values['SOURCE_FETCH_INTERVAL_SECONDS'] = str(max(int(source_fetch_interval_seconds), 0))
        values['BILIBILI_SOURCE_INTERVAL_SECONDS'] = str(max(int(bilibili_source_interval_seconds), 0))
        values['BILIBILI_RETRY_DELAY_SECONDS'] = str(max(int(bilibili_retry_delay_seconds), 0))
        self._write_values(values)

        os.environ['SOURCE_FETCH_INTERVAL_SECONDS'] = values['SOURCE_FETCH_INTERVAL_SECONDS']
        os.environ['BILIBILI_SOURCE_INTERVAL_SECONDS'] = values['BILIBILI_SOURCE_INTERVAL_SECONDS']
        os.environ['BILIBILI_RETRY_DELAY_SECONDS'] = values['BILIBILI_RETRY_DELAY_SECONDS']
        return self.get_fetch_interval_settings()

    def ensure_env_file(self) -> Path:
        if not self.env_file.exists():
            self._write_values(self._load_values())
        return self.env_file

    def _load_values(self) -> dict[str, str]:
        if not self.env_file.exists():
            return {}

        values: dict[str, str] = {}
        for line in self.env_file.read_text(encoding='utf-8-sig').splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or '=' not in stripped:
                continue
            key, value = stripped.split('=', 1)
            key = key.strip()
            value = value.strip()
            if self._is_sensitive_key(key) and value.startswith(_ENC_PREFIX):
                # 启用加密时还原明文;如果 key 已丢失,
                # ``decrypt_text`` 会透传原值并保证向后兼容。
                value = config_encryption.decrypt_text(value[len(_ENC_PREFIX):])
            values[key] = value
        return values

    def _write_values(self, values: dict[str, str]) -> None:
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        # REQ-SEC-001: 启用加密时对敏感字段加『enc:』前缀后落盘;未启用时透传明文。
        encryption_enabled = config_encryption.get_status().enabled
        encoded: dict[str, str] = {}
        for key, raw_value in values.items():
            if (
                encryption_enabled
                and self._is_sensitive_key(key)
                and raw_value
                and not raw_value.startswith(_ENC_PREFIX)
            ):
                encoded[key] = _ENC_PREFIX + config_encryption.encrypt_text(raw_value)
            else:
                encoded[key] = raw_value

        lines: list[str] = []
        emitted: set[str] = set()

        for key in ENV_OUTPUT_ORDER:
            if key in encoded:
                lines.append(f'{key}={encoded[key]}')
                emitted.add(key)

        for key in sorted(encoded):
            if key in emitted:
                continue
            lines.append(f'{key}={encoded[key]}')

        if not lines:
            for key in MANAGED_KEYS:
                lines.append(f'{key}=')

        content = '\n'.join(lines) + '\n'
        lock_path = self.env_file.with_name(self.env_file.name + '.lock')
        with portalocker.Lock(str(lock_path), 'w', timeout=10):
            tmp_fd, tmp_name = tempfile.mkstemp(
                prefix=self.env_file.name + '.', suffix='.tmp', dir=str(self.env_file.parent)
            )
            try:
                with os.fdopen(tmp_fd, 'w', encoding='utf-8', newline='') as fp:
                    fp.write(content)
                os.replace(tmp_name, self.env_file)
            except Exception:
                Path(tmp_name).unlink(missing_ok=True)
                raise

    def _get_bool(self, value: str | None, default: bool) -> bool:
        if value is None:
            return default
        return value.lower() in {'1', 'true', 'yes', 'on'}

    def _get_int(self, value: str | None, default: int) -> int:
        if value is None:
            return default
        try:
            return max(int(value), 0)
        except ValueError:
            return default

    def _normalize_bilibili_cookie(self, raw_cookie: str) -> str:
        normalized = raw_cookie.strip()
        if not normalized:
            raise ValueError('B站 Cookie 不能为空')

        if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
            normalized = normalized[1:-1].strip()

        normalized = re.sub(r'\s+', ' ', normalized).strip()
        if normalized.startswith('BILIBILI_COOKIE='):
            normalized = normalized.split('=', 1)[1].strip()

        if not normalized:
            raise ValueError('B站 Cookie 不能为空')
        if 'SESSDATA=' not in normalized:
            raise ValueError('Cookie 缺少 SESSDATA，系统未保存')
        return normalized

    def _bilibili_cookie_env_key(self, account_key: str) -> str:
        normalized = self._normalize_account_key(account_key)
        if normalized == 'default':
            return 'BILIBILI_COOKIE'
        suffix = normalized.replace('-', '_').upper()
        return f'BILIBILI_COOKIE__{suffix}'

    @staticmethod
    def _normalize_account_key(account_key: str) -> str:
        normalized = re.sub(r'[^a-z0-9-]+', '-', str(account_key or '').strip().lower())
        normalized = re.sub(r'-{2,}', '-', normalized).strip('-')
        return normalized or 'default'

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        return key in SENSITIVE_KEYS or key.startswith('BILIBILI_COOKIE__')
