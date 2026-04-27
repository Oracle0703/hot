from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import threading
import time
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import get_reports_root
from app.models.job import CollectionJob
from app.models.job_log import JobLog
from app.models.source import Source
from app.services import cancel_registry
from app.services.circuit_breaker_service import CircuitBreakerService
from app.services.content_dispatch_service import ContentDispatchService
from app.services.dingtalk_webhook_service import DingTalkWebhookService
from app.services.failure_classifier import FailureClassifier, FailureCode
from app.services.report_distribution_service import ReportDistributionService
from app.services.report_service import ReportService
from app.services.weekly_cover_cache_service import WeeklyCoverCacheService


class JobRunner:
    def __init__(
        self,
        session_factory: sessionmaker,
        source_executor: Callable[[Source], dict[str, object]],
        notification_scheduler: Callable[[Callable[[], None]], None] | None = None,
        settings_provider: Callable[[], object] | None = None,
        sleeper: Callable[[float], None] | None = None,
        failure_classifier: FailureClassifier | None = None,
        circuit_breaker: CircuitBreakerService | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.source_executor = source_executor
        self.notification_scheduler = notification_scheduler or self._schedule_notification_background
        self.settings_provider = settings_provider or get_settings
        self.sleeper = sleeper or time.sleep
        self.failure_classifier = failure_classifier or FailureClassifier()
        self.circuit_breaker = circuit_breaker or CircuitBreakerService()
        self.reports_root = get_reports_root()

    def run_once(self) -> UUID | None:
        with self.session_factory() as session:
            job = session.scalar(
                select(CollectionJob)
                .where(CollectionJob.status == "pending")
                .order_by(CollectionJob.id.asc())
                .limit(1)
            )
            if job is None:
                return None

            enabled_sources = list(
                session.scalars(
                    select(Source)
                    .where(Source.enabled.is_(True))
                    .where(Source.schedule_group == job.schedule_group_scope if job.schedule_group_scope else True)
                    .where(
                        Source.source_group == job.source_group_scope
                        if job.source_group_scope and not job.schedule_group_scope
                        else True
                    )
                    .order_by(Source.id.asc())
                ).all()
            )
            source_runs: list[dict[str, object]] = []

            job.status = "running"
            job.started_at = datetime.utcnow()
            session.commit()

            cancelled = False
            for index, source in enumerate(enabled_sources):
                if cancel_registry.is_cancelled(job.id):
                    cancelled = True
                    forced = cancel_registry.is_force_cancelled(job.id)
                    session.add(
                        JobLog(
                            job_id=job.id,
                            level="warning",
                            message=(
                                "job cancelled by operator (force, skipped remaining sources)"
                                if forced
                                else "job cancelled by operator (cooperative)"
                            ),
                        )
                    )
                    session.commit()
                    break
                if index > 0:
                    # force=true 跳过节拍 sleep,尽最快送到下一轮 cancel 检查并出循环。
                    if not cancel_registry.is_force_cancelled(job.id):
                        self._sleep_before_source(source)
                job.current_source = source.name
                session.commit()
                breaker_bucket = self._build_circuit_breaker_bucket(source)

                if self.circuit_breaker.is_open(breaker_bucket):
                    job.completed_sources += 1
                    job.failed_sources += 1
                    session.add(
                        JobLog(
                            job_id=job.id,
                            source_id=source.id,
                            level="error",
                            message=f"[{FailureCode.RISK_CONTROL}] source blocked by circuit breaker",
                        )
                    )
                    session.commit()
                    continue

                try:
                    result = self.source_executor(source)
                    self.circuit_breaker.record_success(breaker_bucket)
                    source_runs.append(
                        {
                            "source_id": source.id,
                            "source_name": source.name,
                            "item_count": result.get("item_count", 0),
                            "items": result.get("items", []),
                        }
                    )
                    job.completed_sources += 1
                    job.success_sources += 1
                except Exception as exc:  # noqa: BLE001
                    failure = self.failure_classifier.classify(exc)
                    self.circuit_breaker.record_failure(breaker_bucket, failure.code)
                    job.completed_sources += 1
                    job.failed_sources += 1
                    session.add(
                        JobLog(
                            job_id=job.id,
                            source_id=source.id,
                            level="error",
                            message=f"[{failure.code}] {failure.message}",
                        )
                    )
                session.commit()

            cancel_registry.consume(job.id)
            job.current_source = None
            job.finished_at = datetime.utcnow()
            if cancelled:
                job.status = "cancelled"
            elif job.failed_sources > 0 and job.success_sources == 0:
                job.status = "failed"
            elif job.failed_sources > 0:
                job.status = "partial_success"
            else:
                job.status = "success"

            report_service = ReportService(session, reports_root=self.reports_root)
            try:
                report = report_service.generate_for_job(job, source_runs)
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                job = session.get(CollectionJob, job.id)
                if job is None:
                    raise
                job.current_source = None
                job.finished_at = datetime.utcnow()
                job.status = "failed"
                session.add(
                    JobLog(
                        job_id=job.id,
                        level="error",
                        message=f"report generation failed: {exc}",
                    )
                )
                session.commit()
                raise

            try:
                self._dispatch_content_items(session, report_service.last_content_item_ids)
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                job = session.get(CollectionJob, job.id)
                if job is None:
                    raise
                session.add(
                    JobLog(
                        job_id=job.id,
                        level="warning",
                        message=f"content dispatch failed: {exc}",
                    )
                )
                session.commit()

            try:
                ReportDistributionService().copy_report_to_share_dir(report)
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                job = session.get(CollectionJob, job.id)
                if job is None:
                    raise
                session.add(
                    JobLog(
                        job_id=job.id,
                        level="warning",
                        message=f"report distribution failed: {exc}",
                    )
                )
                session.commit()

            try:
                self._prune_weekly_cover_cache(session)
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                job = session.get(CollectionJob, job.id)
                if job is None:
                    raise
                session.add(
                    JobLog(
                        job_id=job.id,
                        level="warning",
                        message=f"weekly cover cache prune failed: {exc}",
                    )
                )
                session.commit()

            self.notification_scheduler(lambda job_id=job.id: self._notify_job_summary(job_id))
            return job.id

    def _sleep_before_source(self, source: Source) -> None:
        settings = self.settings_provider()
        delay_seconds = float(max(int(getattr(settings, 'source_fetch_interval_seconds', 0) or 0), 0))
        if self._is_bilibili_source(source):
            delay_seconds += float(max(int(getattr(settings, 'bilibili_source_interval_seconds', 0) or 0), 0))
        if delay_seconds > 0:
            self.sleeper(delay_seconds)

    def _is_bilibili_source(self, source: Source) -> bool:
        host = urlsplit(str(getattr(source, 'entry_url', '') or '')).netloc.lower()
        return host.endswith('bilibili.com')

    def _build_circuit_breaker_bucket(self, source: Source) -> str:
        platform = str(getattr(source, "site_name", "") or "").strip().lower()
        if not platform:
            host = urlsplit(str(getattr(source, "entry_url", "") or "")).netloc.lower()
            if host.startswith("www."):
                host = host[4:]
            platform = host.split(".", 1)[0] or "unknown"
        account_key = str(getattr(source, "account_key", "") or "").strip()
        if not account_key:
            account = getattr(source, "account", None)
            if account is not None and getattr(account, "account_key", None):
                account_key = str(account.account_key)
        return f"{platform}:{account_key or 'default'}"

    def _schedule_notification_background(self, task: Callable[[], None]) -> None:
        thread = threading.Thread(target=task, daemon=True)
        thread.start()

    def _dispatch_content_items(self, session, content_item_ids: list[UUID]) -> None:
        if not content_item_ids:
            return
        dispatcher = ContentDispatchService(session, settings=self.settings_provider())
        for content_item_id in content_item_ids:
            dispatcher.dispatch_content_item(content_item_id)

    def _prune_weekly_cover_cache(self, session) -> None:
        settings = self.settings_provider()
        retention_days = int(max(int(getattr(settings, 'weekly_cover_cache_retention_days', 60) or 60), 1))
        WeeklyCoverCacheService(session).prune(max_age_days=retention_days)

    def _notify_job_summary(self, job_id: UUID) -> None:
        with self.session_factory() as session:
            job = session.get(CollectionJob, job_id)
            if job is None:
                return

            notifier = DingTalkWebhookService(session)
            try:
                notified = notifier.notify_job_summary(job)
                if notified:
                    for message in notifier.get_last_sent_messages():
                        sequence = int(message.get('sequence', 0) or 0)
                        total = int(message.get('total', 0) or 0)
                        kind = str(message.get('kind', '') or '')
                        label = str(message.get('label', '') or '')
                        kind_text = 'summary' if kind == 'summary' else f"source {label}".strip()
                        session.add(
                            JobLog(
                                job_id=job.id,
                                level="info",
                                message=f"dingtalk notification sent: {sequence}/{total} {kind_text}",
                            )
                        )
                    session.commit()
                else:
                    skip_reason = notifier.get_skip_reason()
                    if skip_reason:
                        session.add(
                            JobLog(
                                job_id=job.id,
                                level="warning",
                                message=f"dingtalk notification skipped: {skip_reason}",
                            )
                        )
                        session.commit()
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                job = session.get(CollectionJob, job_id)
                if job is None:
                    return
                session.add(
                    JobLog(
                        job_id=job.id,
                        level="warning",
                        message=f"dingtalk notification failed: {exc}",
                    )
                )
                session.commit()
