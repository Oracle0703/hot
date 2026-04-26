from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes_sources import get_db_session
from app.models.subscription import Subscription

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


class SubscriptionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    channel: str = Field(default="dingtalk", min_length=1, max_length=30)
    business_lines: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class SubscriptionRead(BaseModel):
    id: str
    code: str
    channel: str
    business_lines: list[str]
    keywords: list[str]
    enabled: bool
    created_at: datetime


def query_subscriptions(
    session: Session,
    *,
    code: str | None = None,
    channel: str | None = None,
) -> list[Subscription]:
    statement = select(Subscription).order_by(Subscription.code.asc())
    if code and code.strip():
        statement = statement.where(Subscription.code.ilike(f"%{code.strip()}%"))
    if channel and channel.strip():
        statement = statement.where(Subscription.channel == channel.strip())
    return list(session.scalars(statement).all())


@router.get("", response_model=list[SubscriptionRead])
def list_subscriptions(
    code: str | None = None,
    channel: str | None = None,
    session: Session = Depends(get_db_session),
) -> list[SubscriptionRead]:
    items = query_subscriptions(session, code=code, channel=channel)
    return [_serialize_subscription(item) for item in items]


@router.post("", response_model=SubscriptionRead, status_code=status.HTTP_201_CREATED)
def create_subscription(payload: SubscriptionCreate, session: Session = Depends(get_db_session)) -> SubscriptionRead:
    existing = session.scalar(select(Subscription).where(Subscription.code == payload.code.strip()))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="subscription code already exists")

    subscription = Subscription(
        code=payload.code.strip(),
        channel=payload.channel.strip(),
        business_lines=[value.strip() for value in payload.business_lines if str(value).strip()],
        keywords=[value.strip() for value in payload.keywords if str(value).strip()],
    )
    session.add(subscription)
    session.commit()
    session.refresh(subscription)
    return _serialize_subscription(subscription)


def _serialize_subscription(item: Subscription) -> SubscriptionRead:
    return SubscriptionRead(
        id=str(item.id),
        code=item.code,
        channel=item.channel,
        business_lines=list(item.business_lines or []),
        keywords=list(item.keywords or []),
        enabled=bool(item.enabled),
        created_at=item.created_at,
    )
