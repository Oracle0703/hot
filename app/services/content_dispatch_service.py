from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.content_item import ContentItem
from app.models.delivery_record import DeliveryRecord
from app.models.subscription import Subscription
from app.services.dingtalk_webhook_service import DEFAULT_TIMEOUT_SECONDS, DingTalkWebhookService
from app.services.subscription_matcher_service import SubscriptionMatcherService


class ContentDispatchService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        dingtalk_sender=None,
        matcher: SubscriptionMatcherService | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.dingtalk_sender = dingtalk_sender
        self.matcher = matcher or SubscriptionMatcherService(session)

    def dispatch_content_item(self, content_item_id) -> int:
        content_item = self.session.get(ContentItem, content_item_id)
        if content_item is None:
            return 0

        subscriptions = self.matcher.match(content_item)
        if not subscriptions:
            return 0

        helper = DingTalkWebhookService(self.session, settings=self.settings, sender=self.dingtalk_sender)
        if helper.get_skip_reason() is not None or not self.settings.enable_dingtalk_notifier or not self.settings.dingtalk_webhook.strip():
            return 0

        sent_count = 0
        touched_count = 0
        webhook_url = helper._build_webhook_url()
        secret = self.settings.dingtalk_secret.strip() or None

        for subscription in subscriptions:
            existing = self.session.scalar(
                select(DeliveryRecord).where(
                    DeliveryRecord.subscription_id == subscription.id,
                    DeliveryRecord.content_item_id == content_item.id,
                )
            )
            if existing is not None:
                continue
            if subscription.channel == "dingtalk":
                payload = self._build_dingtalk_payload(subscription.code, content_item)
                try:
                    helper.sender(webhook_url, payload, DEFAULT_TIMEOUT_SECONDS, secret)
                except Exception as exc:  # noqa: BLE001
                    self.session.add(
                        DeliveryRecord(
                            subscription_id=subscription.id,
                            content_item_id=content_item.id,
                            status="failed",
                            error_message=str(exc),
                        )
                    )
                    touched_count += 1
                    continue
            else:
                continue
            self.session.add(
                DeliveryRecord(
                    subscription_id=subscription.id,
                    content_item_id=content_item.id,
                    status="sent",
                    error_message=None,
                )
            )
            sent_count += 1
            touched_count += 1

        if touched_count > 0:
            self.session.commit()
        return sent_count

    def retry_delivery_record(self, delivery_record_id) -> bool:
        delivery_record = self.session.get(DeliveryRecord, delivery_record_id)
        if delivery_record is None or delivery_record.status != "failed":
            return False

        subscription = self.session.get(Subscription, delivery_record.subscription_id)
        content_item = self.session.get(ContentItem, delivery_record.content_item_id)
        if subscription is None or content_item is None:
            delivery_record.status = "failed"
            delivery_record.error_message = "delivery target missing"
            self.session.commit()
            return False

        helper = DingTalkWebhookService(self.session, settings=self.settings, sender=self.dingtalk_sender)
        skip_reason = helper.get_skip_reason()
        if skip_reason is not None or not self.settings.enable_dingtalk_notifier or not self.settings.dingtalk_webhook.strip():
            delivery_record.status = "failed"
            delivery_record.error_message = skip_reason or "delivery disabled"
            self.session.commit()
            return False

        if subscription.channel != "dingtalk":
            delivery_record.status = "failed"
            delivery_record.error_message = f"unsupported channel: {subscription.channel}"
            self.session.commit()
            return False

        payload = self._build_dingtalk_payload(subscription.code, content_item)
        webhook_url = helper._build_webhook_url()
        secret = self.settings.dingtalk_secret.strip() or None

        try:
            helper.sender(webhook_url, payload, DEFAULT_TIMEOUT_SECONDS, secret)
        except Exception as exc:  # noqa: BLE001
            delivery_record.status = "failed"
            delivery_record.error_message = str(exc)
            self.session.commit()
            return False

        delivery_record.status = "sent"
        delivery_record.error_message = None
        self.session.commit()
        return True

    def retry_delivery_records(self, delivery_record_ids: list) -> int:
        retried_count = 0
        for delivery_record_id in delivery_record_ids:
            if self.retry_delivery_record(delivery_record_id):
                retried_count += 1
        return retried_count

    def _build_dingtalk_payload(self, subscription_code: str, content_item: ContentItem) -> dict[str, object]:
        title = str(getattr(content_item, "title", "") or "未命名内容")
        url = str(getattr(content_item, "canonical_url", "") or "").strip()
        lines = [f"### 订阅推送 {subscription_code}", ""]
        lines.append(f"- 标题：[{title}]({url})" if url else f"- 标题：{title}")
        excerpt = str(getattr(content_item, "excerpt", "") or "").strip()
        if excerpt:
            lines.append(f"- 摘要：{excerpt}")
        return {
            "msgtype": "markdown",
            "markdown": {
                "title": f"订阅推送 {subscription_code}",
                "text": "\n".join(lines).strip(),
            },
        }
