from __future__ import annotations

from app.services.circuit_breaker_service import CircuitBreakerService
from app.services.failure_classifier import FailureCode


def test_circuit_breaker_opens_after_repeated_risk_control() -> None:
    breaker = CircuitBreakerService(threshold=3)

    for _ in range(3):
        breaker.record_failure("bilibili:single-user", FailureCode.RISK_CONTROL)

    assert breaker.is_open("bilibili:single-user") is True


def test_circuit_breaker_ignores_non_breaking_failures() -> None:
    breaker = CircuitBreakerService(threshold=2)

    breaker.record_failure("bilibili:single-user", FailureCode.AUTH_EXPIRED)
    breaker.record_failure("bilibili:single-user", FailureCode.AUTH_EXPIRED)

    assert breaker.is_open("bilibili:single-user") is False
