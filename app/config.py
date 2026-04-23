from __future__ import annotations

import os
from dataclasses import dataclass

from app.runtime_paths import get_runtime_paths


DEFAULT_APP_NAME = "热点信息采集系统"
DEFAULT_ENVIRONMENT = "development"
DEFAULT_DEBUG = True
DEFAULT_DATABASE_URL = "sqlite:///./data/hot_topics.db"
DEFAULT_REPORTS_ROOT = "outputs/reports"
DEFAULT_ENABLE_SCHEDULER = True
DEFAULT_SCHEDULER_POLL_SECONDS = 30
DEFAULT_ENABLE_DINGTALK_NOTIFIER = False
DEFAULT_DINGTALK_WEBHOOK = ""
DEFAULT_DINGTALK_SECRET = ""
DEFAULT_DINGTALK_KEYWORD = ""
DEFAULT_BILIBILI_COOKIE = ""
DEFAULT_REPORT_SHARE_DIR = ""
DEFAULT_ENABLE_SITE_PROXY_RULES = False
DEFAULT_OUTBOUND_PROXY_URL = ""
DEFAULT_OUTBOUND_PROXY_BYPASS_DOMAINS = "bilibili.com,hdslb.com,bilivideo.com"
DEFAULT_SOURCE_FETCH_INTERVAL_SECONDS = 0
DEFAULT_BILIBILI_SOURCE_INTERVAL_SECONDS = 0
DEFAULT_BILIBILI_RETRY_DELAY_SECONDS = 5


@dataclass(slots=True)
class Settings:
    app_name: str = DEFAULT_APP_NAME
    environment: str = DEFAULT_ENVIRONMENT
    debug: bool = DEFAULT_DEBUG
    database_url: str = DEFAULT_DATABASE_URL
    reports_root: str = DEFAULT_REPORTS_ROOT
    enable_scheduler: bool = DEFAULT_ENABLE_SCHEDULER
    scheduler_poll_seconds: int = DEFAULT_SCHEDULER_POLL_SECONDS
    enable_dingtalk_notifier: bool = DEFAULT_ENABLE_DINGTALK_NOTIFIER
    dingtalk_webhook: str = DEFAULT_DINGTALK_WEBHOOK
    dingtalk_secret: str = DEFAULT_DINGTALK_SECRET
    dingtalk_keyword: str = DEFAULT_DINGTALK_KEYWORD
    bilibili_cookie: str = DEFAULT_BILIBILI_COOKIE
    report_share_dir: str = DEFAULT_REPORT_SHARE_DIR
    enable_site_proxy_rules: bool = DEFAULT_ENABLE_SITE_PROXY_RULES
    outbound_proxy_url: str = DEFAULT_OUTBOUND_PROXY_URL
    outbound_proxy_bypass_domains: str = DEFAULT_OUTBOUND_PROXY_BYPASS_DOMAINS
    source_fetch_interval_seconds: int = DEFAULT_SOURCE_FETCH_INTERVAL_SECONDS
    bilibili_source_interval_seconds: int = DEFAULT_BILIBILI_SOURCE_INTERVAL_SECONDS
    bilibili_retry_delay_seconds: int = DEFAULT_BILIBILI_RETRY_DELAY_SECONDS


def _load_runtime_env_values() -> dict[str, str]:
    env_file = get_runtime_paths().env_file
    if not env_file.exists():
        return {}

    values: dict[str, str] = {}
    for line in env_file.read_text(encoding='utf-8-sig').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, value = stripped.split('=', 1)
        values[key.strip()] = value.strip()
    return values


def _get_env_value(name: str, file_values: dict[str, str], default: str) -> str:
    value = os.getenv(name)
    if value is not None:
        return value
    return file_values.get(name, default)


def _get_bool_env(name: str, default: bool, file_values: dict[str, str] | None = None) -> bool:
    value = os.getenv(name)
    if value is None and file_values is not None:
        value = file_values.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _hydrate_process_env(file_values: dict[str, str]) -> None:
    for key, value in file_values.items():
        os.environ.setdefault(key, value)


def get_settings() -> Settings:
    file_values = _load_runtime_env_values()
    _hydrate_process_env(file_values)
    return Settings(
        app_name=_get_env_value('APP_NAME', file_values, DEFAULT_APP_NAME),
        environment=_get_env_value('APP_ENV', file_values, DEFAULT_ENVIRONMENT),
        debug=_get_bool_env('APP_DEBUG', DEFAULT_DEBUG, file_values),
        database_url=_get_env_value('DATABASE_URL', file_values, DEFAULT_DATABASE_URL),
        reports_root=_get_env_value('REPORTS_ROOT', file_values, DEFAULT_REPORTS_ROOT),
        enable_scheduler=_get_bool_env('ENABLE_SCHEDULER', DEFAULT_ENABLE_SCHEDULER, file_values),
        scheduler_poll_seconds=int(_get_env_value('SCHEDULER_POLL_SECONDS', file_values, str(DEFAULT_SCHEDULER_POLL_SECONDS))),
        enable_dingtalk_notifier=_get_bool_env('ENABLE_DINGTALK_NOTIFIER', DEFAULT_ENABLE_DINGTALK_NOTIFIER, file_values),
        dingtalk_webhook=_get_env_value('DINGTALK_WEBHOOK', file_values, DEFAULT_DINGTALK_WEBHOOK),
        dingtalk_secret=_get_env_value('DINGTALK_SECRET', file_values, DEFAULT_DINGTALK_SECRET),
        dingtalk_keyword=_get_env_value('DINGTALK_KEYWORD', file_values, DEFAULT_DINGTALK_KEYWORD),
        bilibili_cookie=_get_env_value('BILIBILI_COOKIE', file_values, DEFAULT_BILIBILI_COOKIE),
        report_share_dir=_get_env_value('REPORT_SHARE_DIR', file_values, DEFAULT_REPORT_SHARE_DIR),
        enable_site_proxy_rules=_get_bool_env('ENABLE_SITE_PROXY_RULES', DEFAULT_ENABLE_SITE_PROXY_RULES, file_values),
        outbound_proxy_url=_get_env_value('OUTBOUND_PROXY_URL', file_values, DEFAULT_OUTBOUND_PROXY_URL),
        outbound_proxy_bypass_domains=_get_env_value('OUTBOUND_PROXY_BYPASS_DOMAINS', file_values, DEFAULT_OUTBOUND_PROXY_BYPASS_DOMAINS),
        source_fetch_interval_seconds=int(_get_env_value('SOURCE_FETCH_INTERVAL_SECONDS', file_values, str(DEFAULT_SOURCE_FETCH_INTERVAL_SECONDS))),
        bilibili_source_interval_seconds=int(_get_env_value('BILIBILI_SOURCE_INTERVAL_SECONDS', file_values, str(DEFAULT_BILIBILI_SOURCE_INTERVAL_SECONDS))),
        bilibili_retry_delay_seconds=int(_get_env_value('BILIBILI_RETRY_DELAY_SECONDS', file_values, str(DEFAULT_BILIBILI_RETRY_DELAY_SECONDS))),
    )
