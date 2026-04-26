from __future__ import annotations

from sqlalchemy import select

from app.api.routes_sources import SessionFactoryHolder
from app.services.dingtalk_webhook_service import DingTalkWebhookService
from app.models.content_item import ContentItem
from app.models.delivery_record import DeliveryRecord
from app.models.subscription import Subscription
from tests.conftest import create_test_client, make_sqlite_url


def test_delivery_api_lists_delivery_records(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "delivery-api-list.db"))

    with SessionFactoryHolder.factory() as session:
        subscription = Subscription(
            code="hr-daily",
            channel="dingtalk",
            business_lines=["HR情报源"],
            keywords=["校招"],
        )
        content_item = ContentItem(
            dedupe_key="content-1",
            title="校招信息汇总",
            canonical_url="https://example.com/content-1",
            tags=["HR情报源"],
            raw_payload={},
        )
        session.add_all([subscription, content_item])
        session.flush()
        session.add(
            DeliveryRecord(
                subscription_id=subscription.id,
                content_item_id=content_item.id,
                status="sent",
            )
        )
        session.commit()

    response = client.get("/api/deliveries")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["subscription_code"] == "hr-daily"
    assert data[0]["content_title"] == "校招信息汇总"
    assert data[0]["content_url"] == "https://example.com/content-1"
    assert data[0]["status"] == "sent"


def test_delivery_api_filters_by_subscription_code_status_and_channel(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "delivery-api-filter.db"))

    with SessionFactoryHolder.factory() as session:
        target_subscription = Subscription(
            code="hr-daily",
            channel="dingtalk",
            business_lines=["HR情报源"],
            keywords=["校招"],
        )
        other_subscription = Subscription(
            code="market-daily",
            channel="email",
            business_lines=["市场情报源"],
            keywords=["版号"],
        )
        target_content = ContentItem(
            dedupe_key="content-filter-1",
            title="校招信息汇总",
            canonical_url="https://example.com/content-filter-1",
            tags=["HR情报源"],
            raw_payload={},
        )
        other_content = ContentItem(
            dedupe_key="content-filter-2",
            title="版号情报汇总",
            canonical_url="https://example.com/content-filter-2",
            tags=["市场情报源"],
            raw_payload={},
        )
        session.add_all([target_subscription, other_subscription, target_content, other_content])
        session.flush()
        session.add_all(
            [
                DeliveryRecord(
                    subscription_id=target_subscription.id,
                    content_item_id=target_content.id,
                    status="sent",
                ),
                DeliveryRecord(
                    subscription_id=other_subscription.id,
                    content_item_id=other_content.id,
                    status="failed",
                ),
            ]
        )
        session.commit()

    response = client.get("/api/deliveries?subscription_code=hr&status=sent&channel=dingtalk")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["subscription_code"] == "hr-daily"
    assert data[0]["channel"] == "dingtalk"
    assert data[0]["status"] == "sent"


def test_delivery_api_returns_error_message_for_failed_records(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "delivery-api-error-message.db"))

    with SessionFactoryHolder.factory() as session:
        subscription = Subscription(
            code="hr-daily",
            channel="dingtalk",
            business_lines=["HR情报源"],
            keywords=["校招"],
        )
        content_item = ContentItem(
            dedupe_key="content-error-1",
            title="校招信息汇总",
            canonical_url="https://example.com/content-error-1",
            tags=["HR情报源"],
            raw_payload={},
        )
        session.add_all([subscription, content_item])
        session.flush()
        session.add(
            DeliveryRecord(
                subscription_id=subscription.id,
                content_item_id=content_item.id,
                status="failed",
                error_message="webhook failed",
            )
        )
        session.commit()

    response = client.get("/api/deliveries?status=failed")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "failed"
    assert data[0]["error_message"] == "webhook failed"


def test_delivery_api_retries_failed_record(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_DINGTALK_NOTIFIER", "true")
    monkeypatch.setenv("DINGTALK_WEBHOOK", "https://oapi.dingtalk.com/robot/send?access_token=test-token")
    requests: list[dict[str, object]] = []

    def fake_send(self, webhook: str, payload: dict[str, object], timeout_seconds: float, secret: str | None) -> None:
        requests.append({"webhook": webhook, "payload": payload, "secret": secret})

    monkeypatch.setattr(DingTalkWebhookService, "_send_webhook", fake_send)
    client = create_test_client(make_sqlite_url(tmp_path, "delivery-api-retry.db"))

    with SessionFactoryHolder.factory() as session:
        subscription = Subscription(
            code="hr-daily",
            channel="dingtalk",
            business_lines=["HR情报源"],
            keywords=["校招"],
        )
        content_item = ContentItem(
            dedupe_key="content-retry-api-1",
            title="校招信息汇总",
            canonical_url="https://example.com/content-retry-api-1",
            tags=["HR情报源"],
            raw_payload={},
        )
        session.add_all([subscription, content_item])
        session.flush()
        delivery = DeliveryRecord(
            subscription_id=subscription.id,
            content_item_id=content_item.id,
            status="failed",
            error_message="webhook failed",
        )
        session.add(delivery)
        session.commit()
        delivery_id = str(delivery.id)

    response = client.post(f"/api/deliveries/{delivery_id}/retry")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == delivery_id
    assert data["status"] == "sent"
    assert data["error_message"] is None
    assert len(requests) == 1


def test_delivery_api_retries_failed_records_in_batch(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_DINGTALK_NOTIFIER", "true")
    monkeypatch.setenv("DINGTALK_WEBHOOK", "https://oapi.dingtalk.com/robot/send?access_token=test-token")
    requests: list[dict[str, object]] = []

    def fake_send(self, webhook: str, payload: dict[str, object], timeout_seconds: float, secret: str | None) -> None:
        requests.append({"webhook": webhook, "payload": payload, "secret": secret})

    monkeypatch.setattr(DingTalkWebhookService, "_send_webhook", fake_send)
    client = create_test_client(make_sqlite_url(tmp_path, "delivery-api-retry-batch.db"))

    with SessionFactoryHolder.factory() as session:
        target_subscription = Subscription(
            code="hr-daily",
            channel="dingtalk",
            business_lines=["HR情报源"],
            keywords=["校招"],
        )
        other_subscription = Subscription(
            code="market-daily",
            channel="email",
            business_lines=["市场情报源"],
            keywords=["版号"],
        )
        first_content = ContentItem(
            dedupe_key="content-retry-batch-api-1",
            title="校招信息A",
            canonical_url="https://example.com/content-retry-batch-api-1",
            tags=["HR情报源"],
            raw_payload={},
        )
        second_content = ContentItem(
            dedupe_key="content-retry-batch-api-2",
            title="版号信息B",
            canonical_url="https://example.com/content-retry-batch-api-2",
            tags=["市场情报源"],
            raw_payload={},
        )
        session.add_all([target_subscription, other_subscription, first_content, second_content])
        session.flush()
        session.add_all(
            [
                DeliveryRecord(
                    subscription_id=target_subscription.id,
                    content_item_id=first_content.id,
                    status="failed",
                    error_message="webhook failed",
                ),
                DeliveryRecord(
                    subscription_id=other_subscription.id,
                    content_item_id=second_content.id,
                    status="failed",
                    error_message="webhook failed",
                ),
            ]
        )
        session.commit()

    response = client.post("/api/deliveries/retry-failed?subscription_code=hr&channel=dingtalk")

    assert response.status_code == 200
    data = response.json()
    assert data["retried_count"] == 1
    assert len(data["delivery_ids"]) == 1
    assert len(requests) == 1

    with SessionFactoryHolder.factory() as session:
        records = list(session.scalars(select(DeliveryRecord).order_by(DeliveryRecord.created_at.asc())).all())
        assert [record.status for record in records] == ["sent", "failed"]
