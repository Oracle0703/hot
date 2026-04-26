from __future__ import annotations

from dataclasses import dataclass

from app.services.failure_classifier import FailureCode


@dataclass(slots=True)
class _CircuitState:
    failure_count: int = 0
    open: bool = False


class CircuitBreakerService:
    def __init__(self, threshold: int = 3, breaking_codes: tuple[str, ...] = (FailureCode.RISK_CONTROL,)) -> None:
        self.threshold = max(int(threshold), 1)
        self.breaking_codes = tuple(str(code or "").strip().upper() for code in breaking_codes if str(code or "").strip())
        self._states: dict[str, _CircuitState] = {}

    def is_open(self, bucket_key: str) -> bool:
        return self._states.get(bucket_key, _CircuitState()).open

    def record_failure(self, bucket_key: str, failure_code: str) -> None:
        if str(failure_code or "").strip().upper() not in self.breaking_codes:
            return
        state = self._states.setdefault(bucket_key, _CircuitState())
        state.failure_count += 1
        if state.failure_count >= self.threshold:
            state.open = True

    def record_success(self, bucket_key: str) -> None:
        self._states.pop(bucket_key, None)
