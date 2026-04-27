from __future__ import annotations

import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


_ACCOUNT_KEY_SPACE_RE = re.compile(r"[\s_]+")
_ACCOUNT_KEY_STRIP_RE = re.compile(r"[^a-z0-9-]")
_MULTI_HYPHEN_RE = re.compile(r"-{2,}")


def normalize_account_key(value: str) -> str:
    normalized = _ACCOUNT_KEY_SPACE_RE.sub("-", str(value or "").strip().lower())
    normalized = _ACCOUNT_KEY_STRIP_RE.sub("-", normalized)
    normalized = _MULTI_HYPHEN_RE.sub("-", normalized).strip("-")
    if not normalized:
        raise ValueError("account_key 不能为空")
    return normalized


class SiteAccountCreate(BaseModel):
    platform: str = Field(min_length=1, max_length=50)
    account_key: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    is_default: bool = False

    @field_validator("platform")
    @classmethod
    def _normalize_platform(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if not normalized:
            raise ValueError("platform 不能为空")
        return normalized

    @field_validator("account_key")
    @classmethod
    def _normalize_account_key(cls, value: str) -> str:
        return normalize_account_key(value)

    @field_validator("display_name")
    @classmethod
    def _normalize_display_name(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("display_name 不能为空")
        return normalized


class SiteAccountUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None
    is_default: bool | None = None

    @field_validator("display_name")
    @classmethod
    def _normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("display_name 不能为空")
        return normalized


class SiteAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: str
    account_key: str
    display_name: str
    enabled: bool
    is_default: bool
