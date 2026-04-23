from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.runtime_paths import get_runtime_paths
from app.services.bilibili_auth_service import BilibiliBrowserAuthService


def test_bilibili_browser_auth_service_syncs_cookie_and_storage_state(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    monkeypatch.delenv('BILIBILI_COOKIE', raising=False)

    class _FakePage:
        async def goto(self, url: str, wait_until: str, timeout: int):
            return None

        async def close(self) -> None:
            return None

    class _FakeContext:
        def __init__(self) -> None:
            self.pages = [_FakePage()]
            self.storage_state_path = None

        async def cookies(self, urls=None):
            return [
                {'name': 'SESSDATA', 'value': 'test-sess'},
                {'name': 'bili_jct', 'value': 'test-jct'},
                {'name': 'DedeUserID', 'value': '123'},
            ]

        async def storage_state(self, path: str):
            self.storage_state_path = path

        async def close(self) -> None:
            return None

    class _FakeChromium:
        def __init__(self, context: _FakeContext) -> None:
            self.context = context
            self.launch_kwargs = None
            self.user_data_dir = None

        async def launch_persistent_context(self, user_data_dir: str, **kwargs):
            self.user_data_dir = user_data_dir
            self.launch_kwargs = kwargs
            return self.context

    class _FakePlaywrightContext:
        def __init__(self, chromium: _FakeChromium) -> None:
            self._playwright = SimpleNamespace(chromium=chromium)

        async def __aenter__(self):
            return self._playwright

        async def __aexit__(self, exc_type, exc, tb):
            return False

    context = _FakeContext()
    chromium = _FakeChromium(context)
    fake_module = ModuleType('playwright.async_api')
    fake_module.async_playwright = lambda: _FakePlaywrightContext(chromium)
    monkeypatch.setitem(sys.modules, 'playwright.async_api', fake_module)

    result = BilibiliBrowserAuthService().login_and_sync()
    runtime_paths = get_runtime_paths(tmp_path)
    env_text = runtime_paths.env_file.read_text(encoding='utf-8')

    assert result.cookie.startswith('SESSDATA=test-sess')
    assert 'BILIBILI_COOKIE=SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123' in env_text
    assert context.storage_state_path == str(runtime_paths.bilibili_storage_state_file)
    assert chromium.user_data_dir == str(runtime_paths.bilibili_user_data_dir)
    assert chromium.launch_kwargs['headless'] is False


def test_bilibili_browser_auth_service_raises_when_login_times_out(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))

    class _FakePage:
        async def goto(self, url: str, wait_until: str, timeout: int):
            return None

        async def close(self) -> None:
            return None

    class _FakeContext:
        def __init__(self) -> None:
            self.pages = [_FakePage()]

        async def cookies(self, urls=None):
            return []

        async def storage_state(self, path: str):
            return None

        async def close(self) -> None:
            return None

    class _FakeChromium:
        def __init__(self, context: _FakeContext) -> None:
            self.context = context

        async def launch_persistent_context(self, user_data_dir: str, **kwargs):
            return self.context

    class _FakePlaywrightContext:
        def __init__(self, chromium: _FakeChromium) -> None:
            self._playwright = SimpleNamespace(chromium=chromium)

        async def __aenter__(self):
            return self._playwright

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_module = ModuleType('playwright.async_api')
    fake_module.async_playwright = lambda: _FakePlaywrightContext(_FakeChromium(_FakeContext()))
    monkeypatch.setitem(sys.modules, 'playwright.async_api', fake_module)

    with pytest.raises(RuntimeError, match='登录超时|SESSDATA'):
        BilibiliBrowserAuthService(login_timeout_ms=10, poll_interval_ms=1).login_and_sync()
