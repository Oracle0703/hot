from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy.orm import sessionmaker

from app.services.scheduler_service import SchedulerService


class SchedulerLoop:
    def __init__(
        self,
        session_factory: sessionmaker,
        job_dispatcher,
        poll_interval_seconds: int = 30,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.job_dispatcher = job_dispatcher
        self.poll_interval_seconds = poll_interval_seconds
        self.clock = clock or datetime.now
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        # /system/health/extended 通过这两个字段做“调度心跳”与“下次预计触发”自检 (REQ-SCHED-040)。
        self.last_tick_at: datetime | None = None
        self.next_due_at: datetime | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="scheduler-loop", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.poll_interval_seconds + 1)
        self._thread = None

    def run_once(self) -> object | None:
        now = self.clock()
        with self.session_factory() as session:
            created_job = SchedulerService(session).run_due_jobs(now)
        if created_job:
            self.job_dispatcher.dispatch_pending_jobs()
        self.last_tick_at = now
        self.next_due_at = now + timedelta(seconds=self.poll_interval_seconds)
        return created_job

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.run_once()
            self._stop_event.wait(self.poll_interval_seconds)
