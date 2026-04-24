"""阶段 2 — Pydantic 配置 schema(REQ-CFG-001/REQ-CFG-010)。

该模块在保持现有 `app.config.Settings` dataclass 与所有调用方兼容的前提下,
为环境变量 / `data/app.env` 注入提供集中式的:

* 类型与取值校验(基于 Pydantic v2)
* 字段元数据(group/sensitive/description)
* 掩码 / 分组导出 / 配置自检工具

字段定义与 docs/specs/10-runtime-and-config.md 中"配置项总表"对齐;
新增字段请优先在这里加。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

import httpx
import yaml
from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 暴露 ValidationError 方便上层捕获
__all__ = [
    "SettingsSchema",
    "SettingsFieldInfo",
    "ValidationError",
    "mask_value",
    "list_settings_fields",
    "list_settings_groups",
    "export_settings_yaml",
    "self_check_dingtalk_webhook",
]

_HHMM = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")
_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}

GROUP_APP = "app"
GROUP_DATABASE = "database"
GROUP_REPORTS = "reports"
GROUP_SCHEDULER = "scheduler"
GROUP_DINGTALK = "dingtalk"
GROUP_BILIBILI = "bilibili"
GROUP_NETWORK = "network"
GROUP_SOURCE = "source"
GROUP_WEEKLY = "weekly"


def _meta(group: str, *, sensitive: bool = False, description: str = "") -> dict[str, Any]:
    return {
        "group": group,
        "sensitive": sensitive,
        "description": description,
    }


class SettingsSchema(BaseSettings):
    """所有运行期可注入的环境变量集中式声明。"""

    model_config = SettingsConfigDict(
        env_file=None,  # 由 app.config 自行 hydrate,不让 pydantic 反复读文件
        case_sensitive=True,
        extra="ignore",
    )

    # ---- app ----
    app_name: str = Field(default="热点信息采集系统", alias="APP_NAME", json_schema_extra=_meta(GROUP_APP))
    environment: str = Field(default="development", alias="APP_ENV", json_schema_extra=_meta(GROUP_APP))
    debug: bool = Field(default=True, alias="APP_DEBUG", json_schema_extra=_meta(GROUP_APP))

    # ---- database ----
    database_url: str = Field(default="sqlite:///./data/hot_topics.db", alias="DATABASE_URL", json_schema_extra=_meta(GROUP_DATABASE))

    # ---- reports ----
    reports_root: str = Field(default="outputs/reports", alias="REPORTS_ROOT", json_schema_extra=_meta(GROUP_REPORTS))
    report_share_dir: str = Field(default="", alias="REPORT_SHARE_DIR", json_schema_extra=_meta(GROUP_REPORTS))

    # ---- scheduler ----
    enable_scheduler: bool = Field(default=True, alias="ENABLE_SCHEDULER", json_schema_extra=_meta(GROUP_SCHEDULER))
    scheduler_poll_seconds: int = Field(default=30, alias="SCHEDULER_POLL_SECONDS", json_schema_extra=_meta(GROUP_SCHEDULER))
    scheduler_daily_time: str = Field(default="09:00", alias="SCHEDULER_DAILY_TIME", json_schema_extra=_meta(GROUP_SCHEDULER, description="HH:MM"))

    # ---- dingtalk ----
    enable_dingtalk_notifier: bool = Field(default=False, alias="ENABLE_DINGTALK_NOTIFIER", json_schema_extra=_meta(GROUP_DINGTALK))
    dingtalk_webhook: str = Field(default="", alias="DINGTALK_WEBHOOK", json_schema_extra=_meta(GROUP_DINGTALK, sensitive=True))
    dingtalk_secret: str = Field(default="", alias="DINGTALK_SECRET", json_schema_extra=_meta(GROUP_DINGTALK, sensitive=True))
    dingtalk_keyword: str = Field(default="", alias="DINGTALK_KEYWORD", json_schema_extra=_meta(GROUP_DINGTALK))

    # ---- bilibili ----
    bilibili_cookie: str = Field(default="", alias="BILIBILI_COOKIE", json_schema_extra=_meta(GROUP_BILIBILI, sensitive=True))
    bilibili_source_interval_seconds: int = Field(default=0, alias="BILIBILI_SOURCE_INTERVAL_SECONDS", json_schema_extra=_meta(GROUP_BILIBILI))
    bilibili_retry_delay_seconds: int = Field(default=5, alias="BILIBILI_RETRY_DELAY_SECONDS", json_schema_extra=_meta(GROUP_BILIBILI))

    # ---- network ----
    enable_site_proxy_rules: bool = Field(default=False, alias="ENABLE_SITE_PROXY_RULES", json_schema_extra=_meta(GROUP_NETWORK))
    outbound_proxy_url: str = Field(default="", alias="OUTBOUND_PROXY_URL", json_schema_extra=_meta(GROUP_NETWORK, sensitive=True))
    outbound_proxy_bypass_domains: str = Field(default="bilibili.com,hdslb.com,bilivideo.com", alias="OUTBOUND_PROXY_BYPASS_DOMAINS", json_schema_extra=_meta(GROUP_NETWORK))

    # ---- source ----
    source_fetch_interval_seconds: int = Field(default=0, alias="SOURCE_FETCH_INTERVAL_SECONDS", json_schema_extra=_meta(GROUP_SOURCE))

    # ---- weekly ----
    weekly_cover_cache_retention_days: int = Field(default=60, alias="WEEKLY_COVER_CACHE_RETENTION_DAYS", json_schema_extra=_meta(GROUP_WEEKLY))
    weekly_grade_push_threshold: str = Field(default="B+", alias="WEEKLY_GRADE_PUSH_THRESHOLD", json_schema_extra=_meta(GROUP_WEEKLY))

    # ---------- 字段级校验 ----------
    @field_validator("debug", "enable_scheduler", "enable_dingtalk_notifier", "enable_site_proxy_rules", mode="before")
    @classmethod
    def _coerce_bool(cls, value: Any) -> Any:
        if isinstance(value, bool) or value is None:
            return value
        text = str(value).strip().lower()
        if text in _TRUTHY:
            return True
        if text in _FALSY:
            return False
        raise ValueError(f"BOOL_INVALID: 期望 1/yes/true/on 或 0/no/false/off,收到 {value!r}")

    @field_validator("scheduler_poll_seconds", "source_fetch_interval_seconds",
                     "bilibili_source_interval_seconds", "bilibili_retry_delay_seconds",
                     "weekly_cover_cache_retention_days", mode="before")
    @classmethod
    def _coerce_int(cls, value: Any) -> Any:
        if value is None or isinstance(value, int):
            return value
        text = str(value).strip()
        if not text:
            return 0
        if not re.fullmatch(r"-?\d+", text):
            raise ValueError(f"INT_INVALID: 期望整数字符串,收到 {value!r}")
        return int(text)

    @field_validator("dingtalk_webhook", "outbound_proxy_url", mode="after")
    @classmethod
    def _validate_optional_url(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            return ""
        if not re.match(r"^https?://", text, flags=re.IGNORECASE):
            raise ValueError("URL_SCHEME_NOT_ALLOWED: 仅允许 http(s) 协议")
        return text

    @field_validator("scheduler_daily_time", mode="after")
    @classmethod
    def _validate_daily_time(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            return "09:00"
        if not _HHMM.fullmatch(text):
            raise ValueError("DAILY_TIME_INVALID: 期望 HH:MM (00-23:00-59)")
        return text

    @field_validator("bilibili_cookie", mode="after")
    @classmethod
    def _validate_bilibili_cookie(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            return ""
        if "SESSDATA=" not in text:
            raise ValueError("BILIBILI_COOKIE_MISSING_SESSDATA: cookie 必须包含 SESSDATA=")
        return text


# ---------- 字段元数据 ----------
@dataclass(slots=True, frozen=True)
class SettingsFieldInfo:
    name: str
    env_var: str
    group: str
    sensitive: bool
    description: str
    default: Any


def list_settings_fields() -> list[SettingsFieldInfo]:
    """枚举 SettingsSchema 的全部字段元数据。"""
    out: list[SettingsFieldInfo] = []
    for name, field in SettingsSchema.model_fields.items():
        meta = (field.json_schema_extra or {}) if isinstance(field.json_schema_extra, dict) else {}
        env_var = field.alias or name.upper()
        out.append(
            SettingsFieldInfo(
                name=name,
                env_var=env_var,
                group=str(meta.get("group", "misc")),
                sensitive=bool(meta.get("sensitive", False)),
                description=str(meta.get("description", "")),
                default=field.default,
            )
        )
    return out


def list_settings_groups() -> dict[str, list[SettingsFieldInfo]]:
    """按 group 分组返回字段(组内按 name 字典序)。"""
    grouped: dict[str, list[SettingsFieldInfo]] = {}
    for info in list_settings_fields():
        grouped.setdefault(info.group, []).append(info)
    for group, items in grouped.items():
        items.sort(key=lambda x: x.name)
    return dict(sorted(grouped.items(), key=lambda kv: kv[0]))


# ---------- 掩码 / 导出 ----------
def mask_value(value: str | None, *, sensitive: bool = True) -> str:
    """脱敏:< 8 位 → '***';>= 8 位 → 前 4 + ***** + 后 4"""
    if not sensitive:
        return value or ""
    text = value or ""
    if len(text) < 8:
        return "***"
    return f"{text[:4]}*****{text[-4:]}"


def export_settings_yaml(values: dict[str, Any] | None = None, *, mask_sensitive: bool = True) -> str:
    """按 group → field 字典序输出 yaml(常用于 `/system/config/export`)。"""
    fields = list_settings_groups()
    payload: dict[str, dict[str, Any]] = {}
    for group, infos in fields.items():
        payload[group] = {}
        for info in infos:
            raw = (values or {}).get(info.env_var, info.default)
            if info.sensitive and mask_sensitive:
                raw = mask_value(str(raw) if raw is not None else "", sensitive=True)
            payload[group][info.env_var] = raw
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


# ---------- 配置自检 ----------
def self_check_dingtalk_webhook(
    webhook: str,
    *,
    secret: str | None = None,
    timeout_seconds: float = 5.0,
    client_factory: Any = None,
) -> dict[str, Any]:
    """对钉钉 webhook 做一次轻量校验,不实际发送告警(payload 是 ping 文本)。

    返回: {"ok": bool, "status": int|None, "reason": str}
    `client_factory` 注入用,默认是 `httpx.Client`。
    """
    webhook = (webhook or "").strip()
    if not webhook:
        return {"ok": False, "status": None, "reason": "DINGTALK_WEBHOOK_EMPTY"}
    if not re.match(r"^https?://", webhook, flags=re.IGNORECASE):
        return {"ok": False, "status": None, "reason": "URL_SCHEME_NOT_ALLOWED"}

    payload = {"msgtype": "text", "text": {"content": "[hot-collector] config self-check ping"}}
    factory = client_factory or (lambda **kw: httpx.Client(**kw))
    try:
        with factory(timeout=timeout_seconds) as client:
            resp = client.post(webhook, json=payload)
            ok = resp.status_code == 200
            return {
                "ok": ok,
                "status": resp.status_code,
                "reason": "OK" if ok else f"HTTP_{resp.status_code}",
            }
    except Exception as exc:  # pragma: no cover - 环境异常
        return {"ok": False, "status": None, "reason": f"REQUEST_FAILED:{type(exc).__name__}"}


def _resolve_group_iter(groups: Iterable[str] | None) -> list[str]:  # pragma: no cover - 备用
    fields = list_settings_groups()
    if not groups:
        return list(fields.keys())
    return [g for g in groups if g in fields]
