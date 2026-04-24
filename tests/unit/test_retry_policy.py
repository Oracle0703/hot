"""TC-DISP-001~005 — RetryPolicy 单元测试。"""

from __future__ import annotations

import pytest

from app.services.retry_policy import RetryPolicy, DEFAULT_RETRY_ON
from app.services.strategies.registry import ReasonCode, StrategyError


def test_default_policy_runs_once() -> None:
    """TC-DISP-001"""
    policy = RetryPolicy.from_dict(None)
    assert policy.max_attempts == 1
    assert policy.retry_on == DEFAULT_RETRY_ON

    calls = {"n": 0}
    def work():
        calls["n"] += 1
        return "ok"
    assert policy.run(work, sleep=lambda s: None) == "ok"
    assert calls["n"] == 1


def test_network_error_triggers_retry_until_success() -> None:
    """TC-DISP-002"""
    policy = RetryPolicy.from_dict({"max_attempts": 3, "retry_on": ["NETWORK"], "backoff_seconds": 0})
    seq = iter([
        StrategyError(ReasonCode.NETWORK, "boom"),
        "second-time",
    ])

    def work():
        nxt = next(seq)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    assert policy.run(work, sleep=lambda s: None) == "second-time"


def test_parse_error_does_not_trigger_retry() -> None:
    """TC-DISP-003"""
    policy = RetryPolicy.from_dict({"max_attempts": 3, "retry_on": ["NETWORK"], "backoff_seconds": 0})
    calls = {"n": 0}

    def work():
        calls["n"] += 1
        raise StrategyError(ReasonCode.PARSE, "bad html")

    with pytest.raises(StrategyError) as exc_info:
        policy.run(work, sleep=lambda s: None)
    assert exc_info.value.reason_code == ReasonCode.PARSE
    assert calls["n"] == 1


def test_exhausted_attempts_marks_failure() -> None:
    """TC-DISP-004"""
    policy = RetryPolicy.from_dict({"max_attempts": 2, "retry_on": ["NETWORK"], "backoff_seconds": 0})
    calls = {"n": 0}

    def work():
        calls["n"] += 1
        raise StrategyError(ReasonCode.NETWORK, "always fails")

    with pytest.raises(StrategyError) as exc_info:
        policy.run(work, sleep=lambda s: None)
    assert exc_info.value.reason_code == ReasonCode.NETWORK
    assert calls["n"] == 2


def test_backoff_is_exponential() -> None:
    """TC-DISP-005: backoff_seconds=1 -> 第一次重试等 1s, 第二次等 2s"""
    policy = RetryPolicy.from_dict({"max_attempts": 3, "retry_on": ["NETWORK"], "backoff_seconds": 1.0})
    waits: list[float] = []

    def work():
        raise StrategyError(ReasonCode.NETWORK, "boom")

    with pytest.raises(StrategyError):
        policy.run(work, sleep=lambda s: waits.append(s))
    assert waits == [1.0, 2.0]
