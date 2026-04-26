from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes_sources import get_db_session
from app.models.content_item import ContentItem

router = APIRouter(prefix="/api/content", tags=["content"])


class ContentItemRead(BaseModel):
    id: str
    dedupe_key: str
    title: str
    canonical_url: str
    excerpt: str | None
    tags: list[str]
    updated_at: datetime | None


def query_content_items(
    session: Session,
    *,
    title: str | None = None,
    tag: str | None = None,
) -> list[ContentItem]:
    items = list(
        session.scalars(select(ContentItem).order_by(ContentItem.updated_at.desc(), ContentItem.created_at.desc())).all()
    )
    title_value = (title or "").strip().lower()
    tag_value = (tag or "").strip().lower()
    if title_value:
        items = [item for item in items if title_value in str(item.title or "").lower()]
    if tag_value:
        items = [item for item in items if any(tag_value in str(item_tag or "").lower() for item_tag in (item.tags or []))]
    return items


@router.get("", response_model=list[ContentItemRead])
def list_content(
    title: str | None = None,
    tag: str | None = None,
    session: Session = Depends(get_db_session),
) -> list[ContentItemRead]:
    items = query_content_items(session, title=title, tag=tag)
    return [
        ContentItemRead(
            id=str(item.id),
            dedupe_key=item.dedupe_key,
            title=item.title,
            canonical_url=item.canonical_url,
            excerpt=item.excerpt,
            tags=list(item.tags or []),
            updated_at=item.updated_at,
        )
        for item in items
    ]
