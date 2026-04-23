from __future__ import annotations

import threading


class JobDispatcher:
    def __init__(self, runner) -> None:
        self.runner = runner
        self._lock = threading.Lock()

    def dispatch_pending_jobs(self) -> None:
        if not self._lock.acquire(blocking=False):
            return

        thread = threading.Thread(target=self._run_pending_jobs, daemon=True)
        thread.start()

    def _run_pending_jobs(self) -> None:
        try:
            while self.runner.run_once() is not None:
                continue
        finally:
            self._lock.release()
