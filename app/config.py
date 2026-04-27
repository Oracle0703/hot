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
DEFAULT_WEEKLY_COVER_CACHE_RETENTION_DAYS = 60
DEFAULT_WEEKLY_GRADE_PUSH_THRESHOLD = "B+"


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
    weekly_cover_cache_retention_days: int = DEFAULT_WEEKLY_COVER_CACHE_RETENTION_DAYS
    weekly_grade_push_threshold: str = DEFAULT_WEEKLY_GRADE_PUSH_THRESHOLD


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


def _get_settings_env_keys() -> set[str]:
    try:
        from app.config_schema import SettingsSchema

        keys: set[str] = set()
        for field in SettingsSchema.model_fields.values():
            alias = getattr(field, "alias", None)
            if isinstance(alias, str) and alias:
                keys.add(alias)
        return keys
    except Exception:
        return {
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
            'REPORT_SHARE_DIR',
            'ENABLE_SITE_PROXY_RULES',
            'OUTBOUND_PROXY_URL',
            'OUTBOUND_PROXY_BYPASS_DOMAINS',
            'SOURCE_FETCH_INTERVAL_SECONDS',
            'BILIBILI_SOURCE_INTERVAL_SECONDS',
            'BILIBILI_RETRY_DELAY_SECONDS',
            'WEEKLY_COVER_CACHE_RETENTION_DAYS',
            'WEEKLY_GRADE_PUSH_THRESHOLD',
        }


def _build_settings_schema_input(file_values: dict[str, str]) -> dict[str, str]:
    try:
        from app.config_schema import SettingsSchema

        values: dict[str, str] = {}
        for field in SettingsSchema.model_fields.values():
            alias = getattr(field, "alias", None)
            if not isinstance(alias, str) or not alias:
                continue
            env_value = os.getenv(alias)
            if env_value is not None:
                values[alias] = env_value
                continue
            file_value = file_values.get(alias)
            if file_value is not None:
                values[alias] = file_value
        return values
    except Exception:
        return {}


def _hydrate_process_env(file_values: dict[str, str]) -> None:
    settings_env_keys = _get_settings_env_keys()
    for key, value in file_values.items():
        if key in settings_env_keys:
            continue
        os.environ.setdefault(key, value)


def get_settings() -> Settings:
    file_values = _load_runtime_env_values()
    schema_input = _build_settings_schema_input(file_values)
    _hydrate_process_env(file_values)
    # 优先走 Pydantic schema 验证(REQ-CFG-001):若任何字段非法直接抛 ValidationError,
    # 调用方应在启动期 catch 并落 launcher.log。失败时回退到旧的宽松 dict 解析,
    # 以保证已经在生产运行的旧 app.env(可能含历史脏数据)不会因校验直接拒绝启动。
    try:
        from app.config_schema import SettingsSchema

        schema = SettingsSchema(**schema_input)
        return Settings(
            app_name=schema.app_name,
            environment=schema.environment,
            debug=schema.debug,
            database_url=schema.database_url,
            reports_root=schema.reports_root,
            enable_scheduler=schema.enable_scheduler,
            scheduler_poll_seconds=schema.scheduler_poll_seconds,
            enable_dingtalk_notifier=schema.enable_dingtalk_notifier,
            dingtalk_webhook=schema.dingtalk_webhook,
            dingtalk_secret=schema.dingtalk_secret,
            dingtalk_keyword=schema.dingtalk_keyword,
            bilibili_cookie=schema.bilibili_cookie,
            report_share_dir=schema.report_share_dir,
            enable_site_proxy_rules=schema.enable_site_proxy_rules,
            outbound_proxy_url=schema.outbound_proxy_url,
            outbound_proxy_bypass_domains=schema.outbound_proxy_bypass_domains,
            source_fetch_interval_seconds=schema.source_fetch_interval_seconds,
            bilibili_source_interval_seconds=schema.bilibili_source_interval_seconds,
            bilibili_retry_delay_seconds=schema.bilibili_retry_delay_seconds,
            weekly_cover_cache_retention_days=schema.weekly_cover_cache_retention_days,
            weekly_grade_push_threshold=schema.weekly_grade_push_threshold,
        )
    except Exception:
        # 兼容旧解析 — 详细 fallback 见下方 _legacy_get_settings
        return _legacy_get_settings(file_values)


def _legacy_get_settings(file_values: dict[str, str]) -> Settings:
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
        weekly_cover_cache_retention_days=int(_get_env_value('WEEKLY_COVER_CACHE_RETENTION_DAYS', file_values, str(DEFAULT_WEEKLY_COVER_CACHE_RETENTION_DAYS))),
        weekly_grade_push_threshold=_get_env_value('WEEKLY_GRADE_PUSH_THRESHOLD', file_values, DEFAULT_WEEKLY_GRADE_PUSH_THRESHOLD).strip() or DEFAULT_WEEKLY_GRADE_PUSH_THRESHOLD,
    )
