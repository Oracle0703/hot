"""TC-STRAT-001~006 — 策略注册与统一异常单元测试。"""

from __future__ import annotations

import threading

import pytest

from app.services.strategies.registry import (
    ReasonCode,
    StrategyAlreadyRegistered,
    StrategyCancelled,
    StrategyError,
    StrategyMeta,
    StrategyNotFound,
    StrategyRegistry,
    StrategyResult,
    VALID_REASON_CODES,
    execute_with_cancel_check,
)


class _EchoStrategy:
    def describe(self) -> StrategyMeta:
        return StrategyMeta(name="echo", label="Echo", description="返回固定结果", supports_dry_run=True)

    def fetch(self, source, *, cancel_event=None) -> StrategyResult:
        return StrategyResult(items=[{"title": "ok"}], diagnostics={"hits": 1})


def test_register_decorator_makes_strategy_resolvable_by_name() -> None:
    """TC-STRAT-001"""
    reg = StrategyRegistry()
    reg.register("echo", _EchoStrategy())
    s = reg.get("echo")
    assert s.describe().name == "echo"


def test_duplicate_registration_raises() -> None:
    """TC-STRAT-002"""
    reg = StrategyRegistry()
    reg.register("echo", _EchoStrategy())
    with pytest.raises(StrategyAlreadyRegistered):
        reg.register("echo", _EchoStrategy())


def test_unknown_strategy_raises() -> None:
    """TC-STRAT-003"""
    reg = StrategyRegistry()
    with pytest.raises(StrategyNotFound):
        reg.get("nope")


def test_describe_returns_required_metadata() -> None:
    """TC-STRAT-004"""
    meta = _EchoStrategy().describe()
    assert meta.name and meta.label and meta.description


def test_strategy_error_carries_reason_code() -> None:
    """TC-STRAT-005"""
    err = StrategyError(ReasonCode.NETWORK, "boom")
    assert err.reason_code in VALID_REASON_CODES
    assert err.reason_code == ReasonCode.NETWORK
    bad = StrategyError("MADE_UP_CODE")
    assert bad.reason_code == ReasonCode.UNKNOWN


def test_cancel_event_interrupts_fetch() -> None:
    """TC-STRAT-006"""
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(StrategyCancelled):
        execute_with_cancel_check(cancel, lambda: StrategyResult())
