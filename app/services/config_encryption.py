"""可选的配置静态加密 (Fernet)。

设计要点 (REQ-SEC-001):
- 仅当环境变量 ``CONFIG_ENCRYPTION_KEY`` 设置且为合法 Fernet key 时启用;否则回退明文并记录 warning。
- 使用对称加密 ``cryptography.fernet.Fernet``,密钥长度 32 字节 base64 编码 (44 字符)。
- ``encrypt_text`` / ``decrypt_text`` 是无状态函数,便于在 AppEnvService 写入/读取时调用。
- 提供 ``generate_key`` 便利运维生成密钥。

注:阶段 4 先落地工具函数与单元测试覆盖;接入 AppEnvService 的 read/write 由后续小步骤完成。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Final

from cryptography.fernet import Fernet, InvalidToken

_KEY_ENV: Final[str] = "CONFIG_ENCRYPTION_KEY"
_logger = logging.getLogger("app.config_encryption")
_warned_missing = False


@dataclass(slots=True, frozen=True)
class EncryptionStatus:
    enabled: bool
    reason: str | None


def generate_key() -> str:
    """生成一把新的 Fernet key,运维侧可写入 ``CONFIG_ENCRYPTION_KEY`` 环境变量。"""
    return Fernet.generate_key().decode("ascii")


def _resolve_key() -> str | None:
    raw = os.environ.get(_KEY_ENV)
    if raw is None:
        return None
    cleaned = raw.strip()
    return cleaned or None


def get_status() -> EncryptionStatus:
    key = _resolve_key()
    if key is None:
        return EncryptionStatus(enabled=False, reason="CONFIG_ENCRYPTION_KEY_NOT_SET")
    try:
        Fernet(key.encode("ascii"))
    except (ValueError, TypeError):
        return EncryptionStatus(enabled=False, reason="CONFIG_ENCRYPTION_KEY_INVALID")
    return EncryptionStatus(enabled=True, reason=None)


def _warn_once_if_missing() -> None:
    global _warned_missing
    if _warned_missing:
        return
    _warned_missing = True
    _logger.warning(
        "CONFIG_ENCRYPTION_KEY 未设置,敏感配置将以明文写入磁盘 (符合 REQ-SEC-001 的回退策略)"
    )


def encrypt_text(plain: str) -> str:
    """加密。未启用加密时透传明文并触发一次 warning。"""
    status = get_status()
    if not status.enabled:
        _warn_once_if_missing()
        return plain
    fernet = Fernet(_resolve_key().encode("ascii"))  # type: ignore[union-attr]
    return fernet.encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_text(token: str) -> str:
    """解密。未启用加密时按明文直接返回;若 token 不是合法密文也按明文返回(向后兼容)。"""
    status = get_status()
    if not status.enabled:
        return token
    fernet = Fernet(_resolve_key().encode("ascii"))  # type: ignore[union-attr]
    try:
        return fernet.decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        # 兼容历史明文条目
        return token


def reset_warning_state_for_tests() -> None:
    global _warned_missing
    _warned_missing = False
