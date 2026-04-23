from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CollectionStrategy = Literal["generic_css", "youtube_channel_recent", "bilibili_site_search", "bilibili_profile_videos_recent", "x_profile_recent"]
SourceGroup = Literal["domestic", "overseas"]


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
    collection_strategy: CollectionStrategy = "generic_css"
    search_keyword: str | None = Field(default=None, max_length=200)


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
    collection_strategy: CollectionStrategy | None = None
    search_keyword: str | None = Field(default=None, max_length=200)


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
    collection_strategy: str
    search_keyword: str | None
