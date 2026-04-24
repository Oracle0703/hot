"""阶段 3.2 — 通用采集策略注册表(REQ-STRAT-001 / TC-STRAT-001~006)。

设计原则:
* 与已有的 site-specific 策略(`BilibiliProfileVideosRecentStrategy` 等)解耦,
  本模块只提供"按名字注册并查表"的轻量基础设施。
* 抛出的所有错误统一封装为 `StrategyError(reason_code=...)`,JobRunner 可据此决定是否重试。
* 任何提供 `describe()` + `fetch(source, *, cancel_event=None)` 的对象都可注册(duck typing)。
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


class ReasonCode:
    NETWORK = "NETWORK"
    TIMEOUT = "TIMEOUT"
    PARSE = "PARSE"
    AUTH = "AUTH"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


VALID_REASON_CODES = frozenset(
    {ReasonCode.NETWORK, ReasonCode.TIMEOUT, ReasonCode.PARSE,
     ReasonCode.AUTH, ReasonCode.CANCELLED, ReasonCode.UNKNOWN}
)


class StrategyError(Exception):
    def __init__(self, reason_code: str, message: str = "", *, cause: Exception | None = None):
        if reason_code not in VALID_REASON_CODES:
            reason_code = ReasonCode.UNKNOWN
        super().__init__(message or reason_code)
        self.reason_code = reason_code
        self.cause = cause


class StrategyCancelled(StrategyError):
    def __init__(self, message: str = "cancelled by operator"):
        super().__init__(ReasonCode.CANCELLED, message)


class StrategyNotFound(LookupError):
    pass


class StrategyAlreadyRegistered(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class StrategyMeta:
    name: str
    label: str
    description: str
    requires_browser: bool = False
    supports_dry_run: bool = True


@dataclass(slots=True)
class StrategyResult:
    items: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


class CollectionStrategy(Protocol):
    def describe(self) -> StrategyMeta: ...

    def fetch(self, source, *, cancel_event: threading.Event | None = None) -> StrategyResult: ...


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, Any] = {}

    def register(self, name: str, strategy: Any) -> None:
        if name in self._strategies:
            raise StrategyAlreadyRegistered(f"strategy {name!r} already registered")
        self._strategies[name] = strategy

    def get(self, name: str) -> Any:
        try:
            return self._strategies[name]
        except KeyError:
            raise StrategyNotFound(f"strategy {name!r} not found") from None

    def names(self) -> list[str]:
        return sorted(self._strategies)

    def clear(self) -> None:
        self._strategies.clear()


_default_registry = StrategyRegistry()


def get_registry() -> StrategyRegistry:
    return _default_registry


def register(name: str) -> Callable[[type], type]:
    """类装饰器:`@register("echo")` 自动用空构造函数登记。"""
    def deco(cls: type) -> type:
        instance = cls()  # type: ignore[call-arg]
        _default_registry.register(name, instance)
        return cls
    return deco


def execute_with_cancel_check(
    cancel_event: threading.Event | None,
    work: Callable[[], StrategyResult],
) -> StrategyResult:
    """运行 `work`,在调用前后检查 cancel_event。"""
    if cancel_event is not None and cancel_event.is_set():
        raise StrategyCancelled()
    result = work()
    if cancel_event is not None and cancel_event.is_set():
        raise StrategyCancelled()
    return result


__all__ = [
    "CollectionStrategy",
    "ReasonCode",
    "StrategyAlreadyRegistered",
    "StrategyCancelled",
    "StrategyError",
    "StrategyMeta",
    "StrategyNotFound",
    "StrategyRegistry",
    "StrategyResult",
    "VALID_REASON_CODES",
    "execute_with_cancel_check",
    "get_registry",
    "register",
]
