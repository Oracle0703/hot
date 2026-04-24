from __future__ import annotations

import base64
import hashlib
import hmac
import time
from collections.abc import Callable
from datetime import datetime
from urllib.parse import quote_plus

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.services.bilibili_video_detail_service import fetch_bilibili_video_detail_by_url
from app.config import Settings, get_settings
from app.models.item import CollectedItem
from app.models.job import CollectionJob
from app.models.job_log import JobLog
from app.models.source import Source
from app.services.published_at_display import format_published_at

DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_SEND_INTERVAL_SECONDS = 3.0


def _truncate_seconds_in_text(value: object) -> object:
    """如果文本含 yyyy-mm-dd HH:MM:SS 风格的秒分量，去掉 :SS。其它情况原样返回。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return value
    import re as _re
    return _re.sub(r"(\d{1,2}:\d{2}):\d{2}(?=$|\s|[Z+\-])", r"\1", text)


class DingTalkWebhookService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        sender: Callable[[str, dict[str, object], float, str | None], None] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.sender = sender or self._send_webhook
        self.sleeper = sleeper or time.sleep
        self._last_skip_reason: str | None = None
        self._last_sent_messages: list[dict[str, object]] = []
        self._item_display_overrides: dict[str, dict[str, object]] = {}
        self.detail_fetcher = fetch_bilibili_video_detail_by_url

    def notify_job_summary(self, job: CollectionJob) -> bool:
        self._last_skip_reason = None
        self._last_sent_messages = []
        config_skip_reason = self._get_config_skip_reason()
        if config_skip_reason is not None:
            self._last_skip_reason = config_skip_reason
            return False
        if not self._is_enabled():
            return False
        if self._count_new_items(job) == 0:
            self._last_skip_reason = 'no new collected items in current job'
            return False

        webhook_url = self._build_webhook_url()
        payloads = self._build_payloads(job)
        secret = self.settings.dingtalk_secret.strip() or None
        for index, payload in enumerate(payloads):
            if index > 0:
                self.sleeper(DEFAULT_SEND_INTERVAL_SECONDS)
            self.sender(webhook_url, payload, DEFAULT_TIMEOUT_SECONDS, secret)
            self._last_sent_messages.append(dict(payload.get('_meta', {})))
        return True

    def get_skip_reason(self) -> str | None:
        if self._last_skip_reason is not None:
            return self._last_skip_reason
        return self._get_config_skip_reason()

    def get_last_sent_messages(self) -> list[dict[str, object]]:
        return [dict(message) for message in self._last_sent_messages]

    def _get_config_skip_reason(self) -> str | None:
        webhook = self.settings.dingtalk_webhook.strip()
        enabled = self.settings.enable_dingtalk_notifier
        if not enabled and webhook:
            return 'ENABLE_DINGTALK_NOTIFIER is false'
        if enabled and not webhook:
            return 'DINGTALK_WEBHOOK is empty'
        return None

    def _is_enabled(self) -> bool:
        return self.settings.enable_dingtalk_notifier and bool(self.settings.dingtalk_webhook.strip())

    def _count_new_items(self, job: CollectionJob) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(CollectedItem)
                .where(CollectedItem.first_seen_job_id == job.id)
            )
            or 0
        )

    def _build_webhook_url(self) -> str:
        webhook = self.settings.dingtalk_webhook.strip()
        secret = self.settings.dingtalk_secret.strip()
        if not secret:
            return webhook

        timestamp = str(int(time.time() * 1000))
        sign = self._build_signature(timestamp, secret)
        separator = '&' if '?' in webhook else '?'
        return f"{webhook}{separator}timestamp={quote_plus(timestamp)}&sign={quote_plus(sign)}"

    def _build_signature(self, timestamp: str, secret: str) -> str:
        string_to_sign = f"{timestamp}\n{secret}"
        digest = hmac.new(secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256).digest()
        return base64.b64encode(digest).decode('utf-8')

    def _build_title(self) -> str:
        return '热点报告'

    def _build_payloads(self, job: CollectionJob) -> list[dict[str, object]]:
        new_items = list(
            self.session.scalars(
                select(CollectedItem)
                .where(CollectedItem.first_seen_job_id == job.id)
                .order_by(CollectedItem.first_seen_at.desc(), CollectedItem.last_seen_at.desc())
            ).all()
        )
        missing_items = list(
            self.session.scalars(
                select(CollectedItem)
                .where(CollectedItem.last_seen_job_id != job.id)
                .order_by(CollectedItem.last_seen_at.desc(), CollectedItem.first_seen_at.desc())
            ).all()
        )
        failure_logs = self._list_failed_source_logs(job)
        source_names = self._load_source_display_names(
            new_items + missing_items,
            [log.source_id for log in failure_logs if log.source_id is not None],
        )
        self._item_display_overrides = self._build_item_display_overrides(new_items)
        grouped_new_items = self._group_items_by_source(new_items, source_names)
        total_messages = len(grouped_new_items)

        return [
            self._build_markdown_payload(
                self._build_message_title(index, total_messages, source_name),
                self._build_source_markdown_text(job, source_name, items),
                {
                    'sequence': index,
                    'total': total_messages,
                    'kind': 'source',
                    'label': source_name,
                },
            )
            for index, (_, source_name, items) in enumerate(grouped_new_items, start=1)
        ]

    def _build_message_title(
        self,
        sequence: int,
        total: int,
        label: str,
    ) -> str:
        compact_label = self._compact_text(label)
        if "热点报告" in compact_label:
            return compact_label
        return f"{self._build_title()} {compact_label}"

    def _build_markdown_payload(self, title: str, text: str, meta: dict[str, object]) -> dict[str, object]:
        return {
            'msgtype': 'markdown',
            'markdown': {
                'title': title,
                'text': text,
            },
            '_meta': meta,
        }

    def _list_failed_source_logs(self, job: CollectionJob) -> list[JobLog]:
        return list(
            self.session.scalars(
                select(JobLog)
                .where(
                    JobLog.job_id == job.id,
                    JobLog.level == 'error',
                    JobLog.source_id.is_not(None),
                )
                .order_by(JobLog.created_at.asc())
            ).all()
        )

    def _load_source_names(self, source_ids: list[object]) -> dict[str, str]:
        normalized_ids = sorted({source_id for source_id in source_ids if source_id is not None}, key=str)
        if not normalized_ids:
            return {}
        sources = self.session.scalars(select(Source).where(Source.id.in_(normalized_ids))).all()
        return {str(source.id): source.name for source in sources}

    def _load_source_display_names(
        self,
        items: list[CollectedItem],
        extra_source_ids: list[object],
    ) -> dict[str, str]:
        normalized_ids = sorted(
            {item.source_id for item in items}
            | {source_id for source_id in extra_source_ids if source_id is not None},
            key=str,
        )
        if not normalized_ids:
            return {}

        sources = {
            str(source.id): source
            for source in self.session.scalars(select(Source).where(Source.id.in_(normalized_ids))).all()
        }
        display_names = {source_id: source.name for source_id, source in sources.items()}

        for item in items:
            source_id = str(item.source_id)
            source = sources.get(source_id)
            if source is None or not self._is_bilibili_profile_source(source):
                continue
            author = self._optional_compact_text(getattr(item, "author", None))
            if author:
                display_names[source_id] = author

        return display_names

    def _is_bilibili_profile_source(self, source: Source) -> bool:
        if source.collection_strategy == "bilibili_profile_videos_recent":
            return True
        return str(source.entry_url or "").strip().startswith("https://space.bilibili.com/")

    def _build_source_summary(
        self,
        new_items: list[CollectedItem],
        missing_items: list[CollectedItem],
        failure_logs: list[JobLog],
        source_names: dict[str, str],
    ) -> str:
        ordered_names: list[str] = []
        for source_id in [*(item.source_id for item in new_items), *(item.source_id for item in missing_items), *(log.source_id for log in failure_logs if log.source_id is not None)]:
            name = source_names.get(str(source_id), str(source_id))
            if name not in ordered_names:
                ordered_names.append(name)
        return '、'.join(ordered_names) if ordered_names else '无'

    def _group_items_by_source(
        self,
        items: list[CollectedItem],
        source_names: dict[str, str],
    ) -> list[tuple[str, str, list[CollectedItem]]]:
        grouped_items: dict[str, list[CollectedItem]] = {}
        for item in items:
            grouped_items.setdefault(str(item.source_id), []).append(item)
        ordered_source_ids = sorted(
            grouped_items,
            key=lambda source_id: (source_names.get(source_id, source_id), source_id),
        )
        return [
            (source_id, source_names.get(source_id, source_id), grouped_items[source_id])
            for source_id in ordered_source_ids
        ]

    def _build_source_markdown_text(
        self,
        job: CollectionJob,
        source_name: str,
        items: list[CollectedItem],
    ) -> str:
        lines = [
            f"### {self._build_message_title(1, 1, source_name)}",
            '',
            *self._format_item_lines(items),
        ]
        return '\n'.join(lines)

    def _build_summary_markdown_text(
        self,
        job: CollectionJob,
        title: str,
        grouped_new_items: list[tuple[str, str, list[CollectedItem]]],
        missing_items: list[CollectedItem],
        failure_logs: list[JobLog],
    ) -> str:
        new_items_count = sum(len(items) for _, _, items in grouped_new_items)
        failed_source_count = len({str(log.source_id) for log in failure_logs if log.source_id is not None})
        lines = [
            f"### {title}",
            '',
            f"**来源概览：** {self._build_source_summary([item for _, _, items in grouped_new_items for item in items], missing_items, failure_logs, {source_id: source_name for source_id, source_name, _ in grouped_new_items})}",
            '',
            '#### 本轮汇总',
            f"- 本轮采集来源：{job.total_sources}",
            f"- 有新增的来源：{len(grouped_new_items)}",
            f"- 本轮新增内容：{new_items_count} 条",
            f"- 历史未命中：{len(missing_items)} 条",
            f"- 异常来源：{failed_source_count}",
            '',
            '#### 各来源新增',
            *self._format_source_new_item_lines(grouped_new_items),
            '',
            '#### 异常提醒',
            *self._format_failure_lines(failure_logs),
            '',
            '#### 任务状态',
            f"- 状态：{job.status}",
            f"- 成功来源：{job.success_sources}",
            f"- 失败来源：{job.failed_sources}",
        ]
        return '\n'.join(lines)

    def _format_item_lines(self, items: list[CollectedItem]) -> list[str]:
        if not items:
            return ['- 无']

        lines: list[str] = []
        for index, item in enumerate(items, start=1):
            title_text = self._build_item_title_line(item)
            if lines:
                lines.append("")
            lines.append(f"{index}. {title_text}")
            lines.append("")
            lines.append(self._build_item_stats_line(item))
            cover_line = self._build_item_cover_line(item)
            if cover_line:
                lines.append("")
                lines.append(cover_line)
        return lines

    def _build_item_title_line(self, item: CollectedItem) -> str:
        title_text = self._compact_text(item.title)
        url = self._optional_compact_text(item.url)
        if not url:
            return title_text
        return f"[{title_text}]({url})"

    def _build_item_stats_line(self, item: CollectedItem) -> str:
        override = self._item_display_overrides.get(str(item.id), {})
        line_parts = []
        raw_text = override.get('published_at_text', getattr(item, 'published_at_text', None))
        # 钉钉摘要正文统一截断到分钟级，避免在条目卡片里出现满 14 字节的 yyyy-MM-dd HH:MM:ss
        line_parts.append(
            f"发布时间：{self._format_item_datetime(item.published_at, _truncate_seconds_in_text(raw_text))}"
        )
        for label, key in (('点赞', 'like_count'), ('评论', 'reply_count'), ('播放', 'view_count')):
            value = override.get(key)
            if value is None:
                continue
            line_parts.append(f"{label}：{value}")
        return " | ".join(line_parts)

    def _build_item_cover_line(self, item: CollectedItem) -> str | None:
        override = self._item_display_overrides.get(str(item.id), {})
        cover_image_url = self._optional_compact_text(override.get("cover_image_url", getattr(item, "cover_image_url", None)))
        if not cover_image_url:
            return None
        return f"封面图：{cover_image_url}"

    def _format_source_new_item_lines(
        self,
        grouped_new_items: list[tuple[str, str, list[CollectedItem]]],
    ) -> list[str]:
        if not grouped_new_items:
            return ['- 无']
        return [f"- {source_name}：{len(items)} 条新增" for _, source_name, items in grouped_new_items]

    def _format_failure_lines(self, logs: list[JobLog]) -> list[str]:
        if not logs:
            return ['- 无']

        lines: list[str] = []
        source_names = self._load_source_names([log.source_id for log in logs if log.source_id is not None])
        for log in logs:
            source_name = source_names.get(str(log.source_id), str(log.source_id))
            lines.append(f"- {source_name}：{log.message}")
        return lines

    def _compact_text(self, value: str | None) -> str:
        if not value:
            return '未命名内容'
        return ' '.join(str(value).split())

    def _optional_compact_text(self, value: object) -> str | None:
        text = ' '.join(str(value or '').split())
        return text or None

    def _format_item_datetime(self, value: datetime | None, raw_text: object = None) -> str:
        return format_published_at(value, raw_text)

    def _build_item_display_overrides(self, items: list[CollectedItem]) -> dict[str, dict[str, object]]:
        overrides: dict[str, dict[str, object]] = {}
        for item in items:
            override = self._build_item_display_override(item)
            if override:
                overrides[str(item.id)] = override
        return overrides

    def _build_item_display_override(self, item: CollectedItem) -> dict[str, object]:
        override = {
            "published_at_text": getattr(item, "published_at_text", None),
            "cover_image_url": getattr(item, "cover_image_url", None),
            "like_count": getattr(item, "like_count", None),
            "reply_count": getattr(item, "reply_count", None),
            "view_count": getattr(item, "view_count", None),
        }
        if all(override.get(key) is not None for key in ("like_count", "reply_count", "view_count")):
            return override

        detail = self._fetch_bilibili_video_detail_by_url(self._optional_compact_text(item.url)) or {}
        for key in ("author", "published_at_text", "cover_image_url", "like_count", "reply_count", "view_count"):
            if override.get(key) is None and detail.get(key) is not None:
                override[key] = detail[key]
        return {key: value for key, value in override.items() if value is not None}

    def _fetch_bilibili_video_detail_by_url(self, url: str | None) -> dict[str, object] | None:
        return self.detail_fetcher(url)

    def _send_webhook(self, webhook: str, payload: dict[str, object], timeout_seconds: float, secret: str | None) -> None:
        request_payload = {key: value for key, value in payload.items() if key != '_meta'}
        response = httpx.post(webhook, json=request_payload, timeout=timeout_seconds)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get('errcode') not in (None, 0):
            raise RuntimeError(f"errcode={data.get('errcode')}, errmsg={data.get('errmsg')}")

