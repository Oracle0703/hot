from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.config import Settings
from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.content_item import ContentItem
from app.models.delivery_record import DeliveryRecord
from app.models.subscription import Subscription
from app.services.content_dispatch_service import ContentDispatchService


def setup_database(tmp_path: Path, name: str):
    import os

    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / name).as_posix()}"
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory()


def test_dispatch_service_does_not_send_duplicate_delivery(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "content-dispatch.db")

    with session_factory() as session:
        session.add(
            Subscription(
                code="hr-daily",
                channel="dingtalk",
                business_lines=["hr"],
                keywords=["校招"],
            )
        )
        session.add(
            ContentItem(
                dedupe_key="content-1",
                title="校招信息汇总",
                canonical_url="https://example.com/content-1",
                tags=["hr"],
                raw_payload={},
            )
        )
        session.commit()
        content_item = session.query(ContentItem).filter_by(dedupe_key="content-1").one()
        requests: list[dict[str, object]] = []

        def fake_sender(webhook: str, payload: dict[str, object], timeout_seconds: float, secret: str | None) -> None:
            requests.append({"webhook": webhook, "payload": payload, "secret": secret})

        dispatcher = ContentDispatchService(
            session,
            settings=Settings(
                enable_dingtalk_notifier=True,
                dingtalk_webhook="https://oapi.dingtalk.com/robot/send?access_token=test-token",
            ),
            dingtalk_sender=fake_sender,
        )

        first_count = dispatcher.dispatch_content_item(content_item.id)
        second_count = dispatcher.dispatch_content_item(content_item.id)
        records = session.query(DeliveryRecord).all()

        assert first_count == 1
        assert second_count == 0
        assert len(requests) == 1
        assert len(records) == 1
        parsed = urlparse(requests[0]["webhook"])
        assert parse_qs(parsed.query)["access_token"] == ["test-token"]


def test_dispatch_service_persists_failed_delivery_reason(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "content-dispatch-failed.db")

    with session_factory() as session:
        session.add(
            Subscription(
                code="hr-daily",
                channel="dingtalk",
                business_lines=["hr"],
                keywords=["校招"],
            )
        )
        session.add(
            ContentItem(
                dedupe_key="content-failed-1",
                title="校招信息汇总",
                canonical_url="https://example.com/content-failed-1",
                tags=["hr"],
                raw_payload={},
            )
        )
        session.commit()
        content_item = session.query(ContentItem).filter_by(dedupe_key="content-failed-1").one()

        def fail_sender(webhook: str, payload: dict[str, object], timeout_seconds: float, secret: str | None) -> None:
            raise RuntimeError("webhook failed")

        dispatcher = ContentDispatchService(
            session,
            settings=Settings(
                enable_dingtalk_notifier=True,
                dingtalk_webhook="https://oapi.dingtalk.com/robot/send?access_token=test-token",
            ),
            dingtalk_sender=fail_sender,
        )

        sent_count = dispatcher.dispatch_content_item(content_item.id)
        records = session.query(DeliveryRecord).all()

        assert sent_count == 0
        assert len(records) == 1
        assert records[0].status == "failed"
        assert records[0].error_message == "webhook failed"


def test_dispatch_service_retries_failed_delivery_record(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "content-dispatch-retry.db")

    with session_factory() as session:
        subscription = Subscription(
            code="hr-daily",
            channel="dingtalk",
            business_lines=["hr"],
            keywords=["校招"],
        )
        content_item = ContentItem(
            dedupe_key="content-retry-1",
            title="校招信息汇总",
            canonical_url="https://example.com/content-retry-1",
            tags=["hr"],
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
        requests: list[dict[str, object]] = []

        def fake_sender(webhook: str, payload: dict[str, object], timeout_seconds: float, secret: str | None) -> None:
            requests.append({"webhook": webhook, "payload": payload, "secret": secret})

        dispatcher = ContentDispatchService(
            session,
            settings=Settings(
                enable_dingtalk_notifier=True,
                dingtalk_webhook="https://oapi.dingtalk.com/robot/send?access_token=test-token",
            ),
            dingtalk_sender=fake_sender,
        )

        retried = dispatcher.retry_delivery_record(delivery.id)
        refreshed = session.get(DeliveryRecord, delivery.id)

        assert retried is True
        assert len(requests) == 1
        assert refreshed is not None
        assert refreshed.status == "sent"
        assert refreshed.error_message is None


def test_dispatch_service_retries_multiple_failed_delivery_records(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "content-dispatch-retry-batch.db")

    with session_factory() as session:
        subscription = Subscription(
            code="hr-daily",
            channel="dingtalk",
            business_lines=["hr"],
            keywords=["校招"],
        )
        first_content = ContentItem(
            dedupe_key="content-retry-batch-1",
            title="校招信息A",
            canonical_url="https://example.com/content-retry-batch-1",
            tags=["hr"],
            raw_payload={},
        )
        second_content = ContentItem(
            dedupe_key="content-retry-batch-2",
            title="校招信息B",
            canonical_url="https://example.com/content-retry-batch-2",
            tags=["hr"],
            raw_payload={},
        )
        session.add_all([subscription, first_content, second_content])
        session.flush()
        first_delivery = DeliveryRecord(
            subscription_id=subscription.id,
            content_item_id=first_content.id,
            status="failed",
            error_message="webhook failed",
        )
        second_delivery = DeliveryRecord(
            subscription_id=subscription.id,
            content_item_id=second_content.id,
            status="failed",
            error_message="webhook failed",
        )
        session.add_all([first_delivery, second_delivery])
        session.commit()
        requests: list[dict[str, object]] = []

        def fake_sender(webhook: str, payload: dict[str, object], timeout_seconds: float, secret: str | None) -> None:
            requests.append({"webhook": webhook, "payload": payload, "secret": secret})

        dispatcher = ContentDispatchService(
            session,
            settings=Settings(
                enable_dingtalk_notifier=True,
                dingtalk_webhook="https://oapi.dingtalk.com/robot/send?access_token=test-token",
            ),
            dingtalk_sender=fake_sender,
        )

        retried_count = dispatcher.retry_delivery_records([first_delivery.id, second_delivery.id])
        refreshed_records = session.query(DeliveryRecord).order_by(DeliveryRecord.created_at.asc()).all()

        assert retried_count == 2
        assert len(requests) == 2
        assert [record.status for record in refreshed_records] == ["sent", "sent"]
        assert [record.error_message for record in refreshed_records] == [None, None]
