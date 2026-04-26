from __future__ import annotations

from dataclasses import dataclass

from app.services.strategies.registry import ReasonCode, StrategyError


class FailureCode:
    NETWORK = ReasonCode.NETWORK
    TIMEOUT = ReasonCode.TIMEOUT
    PARSE = ReasonCode.PARSE
    AUTH_EXPIRED = ReasonCode.AUTH_EXPIRED
    AUTH_MISSING = ReasonCode.AUTH_MISSING
    RISK_CONTROL = ReasonCode.RISK_CONTROL
    PERMISSION_DENIED = ReasonCode.PERMISSION_DENIED
    CANCELLED = ReasonCode.CANCELLED
    UNKNOWN = ReasonCode.UNKNOWN


@dataclass(slots=True)
class FailureInfo:
    code: str
    message: str
    cause: Exception | None = None


class FailureClassifier:
    def classify(self, exc: Exception) -> FailureInfo:
        if isinstance(exc, StrategyError):
            code = self._normalize_code(exc.reason_code)
            return FailureInfo(code=code, message=str(exc), cause=exc.cause)

        message = str(exc).strip() or exc.__class__.__name__
        return FailureInfo(code=self._classify_message(message), message=message, cause=exc)

    def _normalize_code(self, code: str) -> str:
        value = str(code or "").strip().upper()
        if value == "AUTH":
            return FailureCode.AUTH_EXPIRED
        if value in {
            FailureCode.NETWORK,
            FailureCode.TIMEOUT,
            FailureCode.PARSE,
            FailureCode.AUTH_EXPIRED,
            FailureCode.AUTH_MISSING,
            FailureCode.RISK_CONTROL,
            FailureCode.PERMISSION_DENIED,
            FailureCode.CANCELLED,
        }:
            return value
        return FailureCode.UNKNOWN

    def _classify_message(self, message: str) -> str:
        lowered = message.lower()
        if any(marker in message for marker in ("权限不足", "没有权限", "无权限")):
            return FailureCode.PERMISSION_DENIED
        if any(marker in message for marker in ("风控", "访问频繁", "访问存在风险", "安全验证")):
            return FailureCode.RISK_CONTROL
        if any(marker in lowered for marker in ("login", "cookie", "sessdata", "auth")) or "登录" in message:
            return FailureCode.AUTH_EXPIRED
        if any(marker in lowered for marker in ("selector", "parse", "html")):
            return FailureCode.PARSE
        return FailureCode.UNKNOWN
