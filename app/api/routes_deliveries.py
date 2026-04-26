from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes_sources import get_db_session
from app.models.content_item import ContentItem
from app.models.delivery_record import DeliveryRecord
from app.models.subscription import Subscription
from app.services.content_dispatch_service import ContentDispatchService

router = APIRouter(prefix="/api/deliveries", tags=["deliveries"])


class DeliveryRecordRead(BaseModel):
    id: str
    subscription_code: str
    channel: str
    content_title: str
    content_url: str
    status: str
    error_message: str | None
    created_at: datetime


class DeliveryBatchRetryResult(BaseModel):
    retried_count: int
    delivery_ids: list[str]


def _serialize_delivery_row(record, subscription_code, channel, content_title, content_url) -> DeliveryRecordRead:
    return DeliveryRecordRead(
        id=str(record.id),
        subscription_code=str(subscription_code),
        channel=str(channel),
        content_title=str(content_title),
        content_url=str(content_url or ""),
        status=str(record.status),
        error_message=str(record.error_message) if record.error_message else None,
        created_at=record.created_at,
    )


def query_delivery_rows(
    session: Session,
    *,
    subscription_code: str | None = None,
    status: str | None = None,
    channel: str | None = None,
    delivery_record_id: UUID | None = None,
):
    statement = (
        select(
            DeliveryRecord,
            Subscription.code,
            Subscription.channel,
            ContentItem.title,
            ContentItem.canonical_url,
        )
        .join(Subscription, Subscription.id == DeliveryRecord.subscription_id)
        .join(ContentItem, ContentItem.id == DeliveryRecord.content_item_id)
        .order_by(DeliveryRecord.created_at.desc())
    )
    if subscription_code and subscription_code.strip():
        pattern = f"%{subscription_code.strip()}%"
        statement = statement.where(Subscription.code.ilike(pattern))
    if status and status.strip():
        statement = statement.where(DeliveryRecord.status == status.strip())
    if channel and channel.strip():
        statement = statement.where(Subscription.channel == channel.strip())
    if delivery_record_id is not None:
        statement = statement.where(DeliveryRecord.id == delivery_record_id)
    return session.execute(statement).all()


@router.get("", response_model=list[DeliveryRecordRead])
def list_deliveries(
    subscription_code: str | None = None,
    status: str | None = None,
    channel: str | None = None,
    session: Session = Depends(get_db_session),
) -> list[DeliveryRecordRead]:
    rows = query_delivery_rows(
        session,
        subscription_code=subscription_code,
        status=status,
        channel=channel,
    )
    return [_serialize_delivery_row(record, subscription_code, channel, content_title, content_url) for record, subscription_code, channel, content_title, content_url in rows]


@router.post("/{delivery_id}/retry", response_model=DeliveryRecordRead)
def retry_delivery(delivery_id: str, session: Session = Depends(get_db_session)) -> DeliveryRecordRead:
    try:
        delivery_uuid = UUID(delivery_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="delivery record not found") from exc

    record = session.get(DeliveryRecord, delivery_uuid)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="delivery record not found")
    if record.status != "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="only failed delivery can be retried")

    ContentDispatchService(session).retry_delivery_record(delivery_uuid)
    rows = query_delivery_rows(session, delivery_record_id=delivery_uuid)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="delivery record not found")
    record_row, subscription_code, channel, content_title, content_url = rows[0]
    return _serialize_delivery_row(record_row, subscription_code, channel, content_title, content_url)


@router.post("/retry-failed", response_model=DeliveryBatchRetryResult)
def retry_failed_deliveries(
    subscription_code: str | None = None,
    status: str | None = None,
    channel: str | None = None,
    session: Session = Depends(get_db_session),
) -> DeliveryBatchRetryResult:
    status_value = (status or "").strip()
    if status_value and status_value != "failed":
        return DeliveryBatchRetryResult(retried_count=0, delivery_ids=[])

    rows = query_delivery_rows(
        session,
        subscription_code=subscription_code,
        status="failed",
        channel=channel,
    )
    delivery_ids = [record.id for record, _, _, _, _ in rows]
    ContentDispatchService(session).retry_delivery_records(delivery_ids)

    refreshed_rows = query_delivery_rows(
        session,
        subscription_code=subscription_code,
        status=None,
        channel=channel,
    )
    refreshed_map = {record.id: record for record, _, _, _, _ in refreshed_rows if record.id in delivery_ids}
    successful_ids = [str(delivery_id) for delivery_id in delivery_ids if getattr(refreshed_map.get(delivery_id), "status", None) == "sent"]
    return DeliveryBatchRetryResult(retried_count=len(successful_ids), delivery_ids=successful_ids)
