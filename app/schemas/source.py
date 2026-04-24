from __future__ import annotations

import os
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

CollectionStrategy = Literal["generic_css", "youtube_channel_recent", "bilibili_site_search", "bilibili_profile_videos_recent", "x_profile_recent"]
SourceGroup = Literal["domestic", "overseas"]

_ALLOWED_URL_SCHEMES_PRODUCTION = {"http", "https"}
_ALLOWED_URL_SCHEMES_DEBUG = {"http", "https", "file"}


def _is_debug_mode() -> bool:
    value = os.environ.get("APP_DEBUG", "true").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _validate_entry_url(value: str | None) -> str | None:
    if value is None:
        return value
    candidate = value.strip()
    if not candidate:
        raise ValueError("entry_url 不能为空")
    parsed = urlsplit(candidate)
    allowed = _ALLOWED_URL_SCHEMES_DEBUG if _is_debug_mode() else _ALLOWED_URL_SCHEMES_PRODUCTION
    if parsed.scheme.lower() not in allowed:
        raise ValueError("URL_SCHEME_NOT_ALLOWED: 仅允许 http(s) 协议")
    if parsed.scheme.lower() in {"http", "https"} and not parsed.netloc:
        raise ValueError("entry_url 缺少 host")
    return candidate


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    site_name: str | None = Field(default=None, max_length=100)
    entry_url: str = Field(min_length=1)
    fetch_mode: str = Field(min_length=1, max_length=20)
    parser_type: str | None = Field(default=None, max_length=50)
    list_selector: str | None = Field(default=None, max_length=200)
    title_selector: str | None = Field(default=None, max_length=200)
    link_selector: str | None = Field(default=None, max_length=200)
    meta_selector: str | None = Field(default=None, max_length=200)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    max_items: int = Field(default=30, ge=1, le=200)
    enabled: bool = True
    source_group: SourceGroup | None = None
    schedule_group: str | None = Field(default=None, max_length=100)
    collection_strategy: CollectionStrategy = "generic_css"
    search_keyword: str | None = Field(default=None, max_length=200)

    @field_validator("entry_url")
    @classmethod
    def _check_entry_url(cls, value: str) -> str:
        result = _validate_entry_url(value)
        assert result is not None
        return result


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    site_name: str | None = Field(default=None, max_length=100)
    entry_url: str | None = Field(default=None, min_length=1)
    fetch_mode: str | None = Field(default=None, min_length=1, max_length=20)
    parser_type: str | None = Field(default=None, max_length=50)
    list_selector: str | None = Field(default=None, max_length=200)
    title_selector: str | None = Field(default=None, max_length=200)
    link_selector: str | None = Field(default=None, max_length=200)
    meta_selector: str | None = Field(default=None, max_length=200)
    include_keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    max_items: int | None = Field(default=None, ge=1, le=200)
    enabled: bool | None = None
    source_group: SourceGroup | None = None
    schedule_group: str | None = Field(default=None, max_length=100)
    collection_strategy: CollectionStrategy | None = None
    search_keyword: str | None = Field(default=None, max_length=200)

    @field_validator("entry_url")
    @classmethod
    def _check_entry_url(cls, value: str | None) -> str | None:
        return _validate_entry_url(value)


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    site_name: str | None
    entry_url: str
    fetch_mode: str
    parser_type: str | None
    list_selector: str | None
    title_selector: str | None
    link_selector: str | None
    meta_selector: str | None
    include_keywords: list[str]
    exclude_keywords: list[str]
    max_items: int
    enabled: bool
    source_group: SourceGroup | None
    schedule_group: str | None
    collection_strategy: str
    search_keyword: str | None
