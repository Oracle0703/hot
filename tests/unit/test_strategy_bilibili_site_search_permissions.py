import asyncio
import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.services.strategies.bilibili_site_search import (
    _ensure_search_page_accessible,
    _PlaywrightBilibiliRunner,
)


def test_bilibili_runner_search_adds_parsed_cookie_to_context(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightBilibiliRunner()
    monkeypatch.setenv("BILIBILI_COOKIE", "SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123")

    class _FakePage:
        async def goto(self, url: str, wait_until: str, timeout: int):
            return None

        async def content(self) -> str:
            return """
            <div class="bili-video-card">
              <a href="/video/BV1TEST" title="测试视频">测试视频</a>
            </div>
            """

        async def close(self) -> None:
            return None

    class _FakeContext:
        def __init__(self) -> None:
            self.cookies = None

        async def add_cookies(self, cookies):
            self.cookies = cookies

        async def new_page(self):
            return _FakePage()

        async def close(self) -> None:
            return None

    class _FakeBrowser:
        def __init__(self) -> None:
            self.context = _FakeContext()

        async def new_context(self, **kwargs):
            return self.context

        async def close(self) -> None:
            return None

    class _FakeChromium:
        def __init__(self, browser: _FakeBrowser) -> None:
            self.browser = browser

        async def launch(self, headless: bool = True):
            return self.browser

    class _FakePlaywrightContext:
        def __init__(self, browser: _FakeBrowser) -> None:
            self._playwright = SimpleNamespace(chromium=_FakeChromium(browser))

        async def __aenter__(self):
            return self._playwright

        async def __aexit__(self, exc_type, exc, tb):
            return False

    browser = _FakeBrowser()

    def fake_async_playwright():
        return _FakePlaywrightContext(browser)

    fake_module = ModuleType("playwright.async_api")
    fake_module.async_playwright = fake_async_playwright
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_module)

    items = asyncio.run(runner._search("游戏 2026-03-25"))

    assert len(items) == 1
    cookie_names = {cookie["name"] for cookie in browser.context.cookies}
    assert cookie_names == {"SESSDATA", "bili_jct", "DedeUserID"}
    assert {cookie["domain"] for cookie in browser.context.cookies} == {".bilibili.com"}


def test_ensure_search_page_accessible_raises_on_permission_denied_page() -> None:
    html = """
    <html>
      <body>
        <main>
          <h1>权限不足</h1>
          <p>你没有权限访问当前页面</p>
        </main>
      </body>
    </html>
    """

    with pytest.raises(RuntimeError, match="BILIBILI_COOKIE"):
        _ensure_search_page_accessible(html)
