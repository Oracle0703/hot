from __future__ import annotations

from app.services.failure_classifier import FailureClassifier, FailureCode
from app.services.strategies.registry import StrategyError


def test_failure_classifier_preserves_strategy_error_code() -> None:
    failure = FailureClassifier().classify(StrategyError(FailureCode.AUTH_EXPIRED, "登录失效"))

    assert failure.code == FailureCode.AUTH_EXPIRED
    assert failure.message == "登录失效"


def test_failure_classifier_maps_permission_error_message() -> None:
    failure = FailureClassifier().classify(RuntimeError("权限不足，无法访问当前页面"))

    assert failure.code == FailureCode.PERMISSION_DENIED
