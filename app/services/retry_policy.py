"""阶段 3.2 — RetryPolicy(REQ-DISP-001 / TC-DISP-001~005)。

提供策略对象与一个轻量执行器,JobRunner 可包装任意 callable:
    RetryPolicy.from_dict(source.retry_policy).run(callable, on_attempt=...)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

from app.services.strategies.registry import ReasonCode, StrategyError

DEFAULT_RETRY_ON = (ReasonCode.NETWORK, ReasonCode.TIMEOUT)


@dataclass(slots=True)
class RetryPolicy:
    max_attempts: int = 1
    retry_on: tuple[str, ...] = DEFAULT_RETRY_ON
    backoff_seconds: float = 1.0  # 第 N 次重试等待 backoff_seconds * (2**(n-1))

    @classmethod
    def from_dict(cls, value: Optional[dict[str, Any]]) -> "RetryPolicy":
        if not value:
            return cls()
        max_attempts = int(value.get("max_attempts", 1))
        if max_attempts < 1:
            max_attempts = 1
        retry_on_raw = value.get("retry_on") or list(DEFAULT_RETRY_ON)
        retry_on = tuple(str(x).upper() for x in retry_on_raw)
        backoff = float(value.get("backoff_seconds", value.get("backoff", 1.0)) or 0.0)
        if backoff < 0:
            backoff = 0.0
        return cls(max_attempts=max_attempts, retry_on=retry_on, backoff_seconds=backoff)

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "retry_on": list(self.retry_on),
            "backoff_seconds": self.backoff_seconds,
        }

    def should_retry(self, reason_code: str, attempt_number: int) -> bool:
        if attempt_number >= self.max_attempts:
            return False
        return reason_code in self.retry_on

    def sleep_for(self, attempt_number: int) -> float:
        """attempt_number 是已完成的重试次数(1=第一次失败后)。"""
        return self.backoff_seconds * (2 ** (attempt_number - 1))

    def run(
        self,
        work: Callable[[], Any],
        *,
        sleep: Callable[[float], None] = time.sleep,
        on_attempt: Optional[Callable[[int, Optional[StrategyError]], None]] = None,
    ) -> Any:
        last_error: Optional[StrategyError] = None
        for attempt in range(1, self.max_attempts + 1):
            if on_attempt:
                on_attempt(attempt, last_error)
            try:
                return work()
            except StrategyError as exc:
                last_error = exc
                if not self.should_retry(exc.reason_code, attempt):
                    raise
                sleep(self.sleep_for(attempt))
        # max_attempts == 0 不会到这里(>=1 强制),但兜底
        if last_error:
            raise last_error
        raise RuntimeError("retry loop ended without execution")


__all__ = ["RetryPolicy", "DEFAULT_RETRY_ON"]
