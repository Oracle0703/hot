"""TC-SEC-101~103 — 配置加密 (Fernet) 单元测试。"""

from __future__ import annotations

import logging

import pytest

from app.services import config_encryption


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    monkeypatch.delenv("CONFIG_ENCRYPTION_KEY", raising=False)
    config_encryption.reset_warning_state_for_tests()
    yield
    config_encryption.reset_warning_state_for_tests()


def test_round_trip_with_valid_key(monkeypatch) -> None:
    """TC-SEC-101: 设置合法 KEY 后 encrypt/decrypt 可往返,密文与明文不同"""
    key = config_encryption.generate_key()
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", key)

    status = config_encryption.get_status()
    assert status.enabled is True

    plain = "SESSDATA=verysecret;DedeUserID=12345"
    token = config_encryption.encrypt_text(plain)
    assert token != plain
    assert config_encryption.decrypt_text(token) == plain


def test_missing_key_falls_back_to_plain_with_warning(caplog, monkeypatch) -> None:
    """TC-SEC-102: 未设置 KEY 时 encrypt 透传明文并触发一次 warning"""
    monkeypatch.delenv("CONFIG_ENCRYPTION_KEY", raising=False)
    status = config_encryption.get_status()
    assert status.enabled is False
    assert status.reason == "CONFIG_ENCRYPTION_KEY_NOT_SET"

    with caplog.at_level(logging.WARNING, logger="app.config_encryption"):
        result = config_encryption.encrypt_text("hello")
    assert result == "hello"
    assert any("CONFIG_ENCRYPTION_KEY" in rec.message for rec in caplog.records)


def test_invalid_key_treated_as_disabled(monkeypatch) -> None:
    """TC-SEC-103: KEY 非法时 status.enabled=False 且 encrypt 回退明文"""
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "not-a-valid-fernet-key")
    status = config_encryption.get_status()
    assert status.enabled is False
    assert status.reason == "CONFIG_ENCRYPTION_KEY_INVALID"
    assert config_encryption.encrypt_text("data") == "data"


def test_decrypt_legacy_plaintext_when_enabled(monkeypatch) -> None:
    """TC-SEC-103b: 启用加密后,对历史明文 token 解密直接返回原值,不抛异常"""
    key = config_encryption.generate_key()
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", key)
    legacy_plain = "OLD_PLAINTEXT_VALUE"
    assert config_encryption.decrypt_text(legacy_plain) == legacy_plain
