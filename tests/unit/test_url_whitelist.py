"""TC-SEC-001~003 — URL 白名单测试。

策略:DEBUG 模式额外放行 file:// 以兼容本地 HTML 测试夹具;
生产 (APP_DEBUG=false) 仅 http/https。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.source import SourceCreate, SourceUpdate


def _base_payload(**overrides):
    payload = {
        "name": "demo",
        "entry_url": "https://example.com/topics",
        "fetch_mode": "static",
        "collection_strategy": "generic_css",
    }
    payload.update(overrides)
    return payload


def test_file_scheme_rejected_in_production(monkeypatch) -> None:
    """TC-SEC-001: 生产模式 (APP_DEBUG=false) 创建 source 使用 file:// 时抛 URL_SCHEME_NOT_ALLOWED"""
    monkeypatch.setenv("APP_DEBUG", "false")
    with pytest.raises(ValidationError) as exc_info:
        SourceCreate(**_base_payload(entry_url="file:///etc/passwd"))
    assert "URL_SCHEME_NOT_ALLOWED" in str(exc_info.value)


def test_gopher_scheme_rejected_always(monkeypatch) -> None:
    """TC-SEC-002: gopher:// 在 DEBUG/生产 都被拒绝"""
    monkeypatch.setenv("APP_DEBUG", "true")
    with pytest.raises(ValidationError) as exc_info:
        SourceCreate(**_base_payload(entry_url="gopher://example.com/0"))
    assert "URL_SCHEME_NOT_ALLOWED" in str(exc_info.value)

    monkeypatch.setenv("APP_DEBUG", "false")
    with pytest.raises(ValidationError):
        SourceCreate(**_base_payload(entry_url="gopher://example.com/0"))


def test_https_passes() -> None:
    """TC-SEC-003: https://example.com 通过"""
    source = SourceCreate(**_base_payload(entry_url="https://example.com/list"))
    assert source.entry_url == "https://example.com/list"


def test_file_scheme_allowed_in_debug(monkeypatch, tmp_path) -> None:
    """TC-SEC-003a: DEBUG 模式放行 file:// 用于本地 HTML 测试夹具"""
    monkeypatch.setenv("APP_DEBUG", "true")
    fixture = tmp_path / "topic.html"
    fixture.write_text("<html></html>", encoding="utf-8")
    source = SourceCreate(**_base_payload(entry_url=fixture.resolve().as_uri()))
    assert source.entry_url.startswith("file://")


def test_update_partial_with_invalid_scheme_rejected(monkeypatch) -> None:
    """TC-SEC-003b: SourceUpdate 部分更新同样校验 (生产)"""
    monkeypatch.setenv("APP_DEBUG", "false")
    with pytest.raises(ValidationError):
        SourceUpdate(entry_url="javascript:alert(1)")


def test_update_with_none_entry_url_passes_through() -> None:
    """TC-SEC-003c: SourceUpdate.entry_url=None 不触发校验(局部更新)"""
    update = SourceUpdate(entry_url=None)
    assert update.entry_url is None
