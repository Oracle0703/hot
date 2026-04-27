from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.item import CollectedItem
from app.services.dingtalk_webhook_service import (
    DEFAULT_TIMEOUT_SECONDS,
    DingTalkWebhookService,
)
from app.services.published_at_display import format_published_at
from app.services.weekly_rating_service import WeeklyRatingService


class WeeklyPushPreviewSummary(dict):
    pass


class WeeklyDingTalkPushService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        sender=None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.sender = sender or self._send
        self.rating_service = WeeklyRatingService(session)

    def build_preview_markdown(
        self,
        item_ids: list[object],
        *,
        items: list[CollectedItem] | None = None,
    ) -> tuple[str | None, int]:
        eligible_items, markdown = self.build_preview_context(item_ids, items=items)
        if not eligible_items:
            return None, 0
        return markdown, len(eligible_items)

    def build_preview_context(
        self,
        item_ids: list[object],
        *,
        items: list[CollectedItem] | None = None,
    ) -> tuple[list[CollectedItem], str, WeeklyPushPreviewSummary]:
        summary = self.build_preview_summary(item_ids, items=items)
        eligible_items = summary["eligible_items"]
        if not eligible_items:
            return [], "", summary
        payload = self._build_payload(eligible_items)
        markdown = payload.get("markdown", {}).get("text", "")
        return eligible_items, str(markdown), summary

    def build_preview_summary(
        self,
        item_ids: list[object],
        *,
        items: list[CollectedItem] | None = None,
    ) -> WeeklyPushPreviewSummary:
        normalized_ids = [item_id for item_id in item_ids if item_id is not None]
        if not normalized_ids:
            return WeeklyPushPreviewSummary(
                eligible_items=[],
                eligible_count=0,
                skipped_below_threshold_count=0,
                skipped_already_pushed_count=0,
            )

        loaded_items = items
        if loaded_items is None:
            loaded_items = list(
                self.session.scalars(
                    select(CollectedItem)
                    .where(CollectedItem.id.in_(normalized_ids))
                    .order_by(CollectedItem.first_seen_at.desc(), CollectedItem.last_seen_at.desc())
                ).all()
            )
        threshold = self.rating_service.normalize_grade(self.settings.weekly_grade_push_threshold) or "B+"
        eligible_items: list[CollectedItem] = []
        skipped_below_threshold_count = 0
        skipped_already_pushed_count = 0
        for item in loaded_items:
            if getattr(item, "pushed_to_dingtalk_at", None) is not None:
                skipped_already_pushed_count += 1
                continue
            if not self.rating_service.is_grade_at_least(getattr(item, "manual_grade", None), threshold):
                skipped_below_threshold_count += 1
                continue
            eligible_items.append(item)
        return WeeklyPushPreviewSummary(
            eligible_items=eligible_items,
            eligible_count=len(eligible_items),
            skipped_below_threshold_count=skipped_below_threshold_count,
            skipped_already_pushed_count=skipped_already_pushed_count,
        )

    def push_items(self, item_ids: list[object]) -> int:
        helper = DingTalkWebhookService(self.session, settings=self.settings, sender=self.sender)
        if helper.get_skip_reason() is not None or not self.settings.enable_dingtalk_notifier or not self.settings.dingtalk_webhook.strip():
            return 0

        eligible_items = self._get_eligible_items(item_ids)
        if not eligible_items:
            return 0

        payload = self._build_payload(eligible_items)
        webhook_url = helper._build_webhook_url()
        secret = self.settings.dingtalk_secret.strip() or None
        self.sender(webhook_url, payload, DEFAULT_TIMEOUT_SECONDS, secret)

        batch_id = uuid4().hex
        pushed_at = datetime.utcnow()
        for item in eligible_items:
            item.pushed_to_dingtalk_at = pushed_at
            item.pushed_to_dingtalk_batch_id = batch_id
        self.session.commit()
        return len(eligible_items)

    def _get_eligible_items(
        self,
        item_ids: list[object],
        *,
        items: list[CollectedItem] | None = None,
    ) -> list[CollectedItem]:
        return self.build_preview_summary(item_ids, items=items)["eligible_items"]

    def _build_payload(self, items: list[CollectedItem]) -> dict[str, object]:
        lines = ["### 热点报告 筛选结果", ""]
        for index, item in enumerate(items, start=1):
            title = str(getattr(item, "title", "") or "未命名内容")
            url = str(getattr(item, "url", "") or "").strip()
            title_line = f"{index}. [{title}]({url})" if url else f"{index}. {title}"
            lines.append(title_line)
            lines.append(f"评分：{getattr(item, 'manual_grade', None) or '--'}")
            lines.append(
                f"发布时间：{format_published_at(getattr(item, 'published_at', None), getattr(item, 'published_at_text', None))}"
            )
            lines.append(
                f"点赞：{self._metric_text(getattr(item, 'like_count', None))} | 评论：{self._metric_text(getattr(item, 'reply_count', None))} | 播放：{self._metric_text(getattr(item, 'view_count', None))}"
            )
            lines.append("")
        return {
            "msgtype": "markdown",
            "markdown": {
                "title": "热点报告 筛选结果",
                "text": "\n".join(lines).strip(),
            },
        }

    def _metric_text(self, value: int | None) -> str:
        return "--" if value is None else str(value)

    @staticmethod
    def _send(webhook: str, payload: dict[str, object], timeout_seconds: float, secret: str | None) -> None:
        request_payload = dict(payload)
        request_payload.pop("_meta", None)
        response = httpx.post(webhook, json=request_payload, timeout=timeout_seconds)
        response.raise_for_status()
