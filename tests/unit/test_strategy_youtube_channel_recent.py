import asyncio
import sys
from datetime import date
from types import ModuleType, SimpleNamespace

import pytest

from app.services.strategies.youtube_channel_recent import (
    YouTubeChannelRecentStrategy,
    _build_section_url,
    _extract_youtube_items,
    _PlaywrightYouTubeRunner,
)


class _FakeYouTubeRunner:
    def __init__(self, items_by_section) -> None:
        self.items_by_section = items_by_section
        self.requested_sections: list[str] = []

    def fetch_items(self, source, section: str):
        self.requested_sections.append(section)
        return list(self.items_by_section.get(section, []))


def test_youtube_strategy_filters_items_older_than_365_days() -> None:
    runner = _FakeYouTubeRunner(
        {
            "videos": [
                {
                    "title": "边界内视频",
                    "url": "https://youtube.com/watch?v=keep",
                    "published_at": "2025-03-25",
                    "excerpt": "keep",
                },
                {
                    "title": "边界外视频",
                    "url": "https://youtube.com/watch?v=drop",
                    "published_at": "2025-03-24",
                    "excerpt": "drop",
                },
            ],
            "shorts": [],
            "streams": [],
        }
    )
    strategy = YouTubeChannelRecentStrategy(runner=runner, today=date(2026, 3, 25))
    source = SimpleNamespace(entry_url="https://www.youtube.com/@ElectronicArts", max_items=10)

    items = strategy.execute(source)

    assert [item["url"] for item in items] == ["https://youtube.com/watch?v=keep"]
    assert items[0]["published_at"] == "2025-03-25"


def test_youtube_strategy_merges_all_sections_and_deduplicates_by_url() -> None:
    runner = _FakeYouTubeRunner(
        {
            "videos": [
                {
                    "title": "主视频",
                    "url": "https://youtube.com/watch?v=shared",
                    "published_at": "2026-03-24",
                }
            ],
            "shorts": [
                {
                    "title": "Shorts 更新",
                    "url": "https://youtube.com/shorts/unique",
                    "published_at": "2026-03-23",
                }
            ],
            "streams": [
                {
                    "title": "直播回放",
                    "url": "https://youtube.com/watch?v=shared",
                    "published_at": "2026-03-22",
                },
                {
                    "title": "独立直播",
                    "url": "https://youtube.com/watch?v=stream",
                    "published_at": "2026-03-21",
                },
            ],
        }
    )
    strategy = YouTubeChannelRecentStrategy(runner=runner, today=date(2026, 3, 25))
    source = SimpleNamespace(entry_url="https://www.youtube.com/@EpicGames", max_items=10)

    items = strategy.execute(source)

    assert runner.requested_sections == ["videos", "shorts", "streams"]
    assert [item["url"] for item in items] == [
        "https://youtube.com/watch?v=shared",
        "https://youtube.com/shorts/unique",
        "https://youtube.com/watch?v=stream",
    ]


def test_youtube_strategy_returns_empty_when_max_items_is_not_positive() -> None:
    runner = _FakeYouTubeRunner(
        {
            "videos": [
                {
                    "title": "不会返回",
                    "url": "https://youtube.com/watch?v=ignored",
                    "published_at": "2026-03-24",
                }
            ],
            "shorts": [],
            "streams": [],
        }
    )
    strategy = YouTubeChannelRecentStrategy(runner=runner, today=date(2026, 3, 25))

    items = strategy.execute(SimpleNamespace(entry_url="https://www.youtube.com/@Channel", max_items=0))

    assert items == []


def test_youtube_strategy_accepts_english_absolute_date() -> None:
    runner = _FakeYouTubeRunner(
        {
            "videos": [
                {
                    "title": "英文日期视频",
                    "url": "https://youtube.com/watch?v=abs-date",
                    "published_at": "Mar 1, 2026",
                }
            ],
            "shorts": [],
            "streams": [],
        }
    )
    strategy = YouTubeChannelRecentStrategy(runner=runner, today=date(2026, 3, 25))

    items = strategy.execute(SimpleNamespace(entry_url="https://www.youtube.com/@Channel", max_items=10))

    assert [item["url"] for item in items] == ["https://youtube.com/watch?v=abs-date"]


def test_extract_youtube_items_prefers_date_token_over_views() -> None:
    html = """
    <ytd-rich-item-renderer>
      <a id="video-title" href="/watch?v=abc" title="测试视频">测试视频</a>
      <div id="metadata-line">
        <span>1.2M views</span>
        <span>3 days ago</span>
      </div>
    </ytd-rich-item-renderer>
    """

    items = _extract_youtube_items(html, "videos")

    assert items[0]["published_at"] == "3 days ago"


def test_build_section_url_preserves_query_string() -> None:
    url = _build_section_url("https://www.youtube.com/@ElectronicArts?persist=1", "videos")

    assert url == "https://www.youtube.com/@ElectronicArts/videos?persist=1"


def test_youtube_runner_fetch_items_can_run_inside_running_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightYouTubeRunner()

    async def fake_fetch_items(source, section: str):
        return [{"title": "loop", "url": "https://youtube.com/watch?v=loop", "published_at": "2026-03-24"}]

    monkeypatch.setattr(runner, "_fetch_items", fake_fetch_items)

    async def invoke():
        return runner.fetch_items(SimpleNamespace(entry_url="https://www.youtube.com/@Loop"), "videos")

    items = asyncio.run(invoke())

    assert items[0]["url"] == "https://youtube.com/watch?v=loop"


def test_youtube_runner_creates_page_with_ignore_https_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightYouTubeRunner()

    class _FakeBody:
        async def inner_text(self) -> str:
            return "Channel page"

    class _FakePage:
        async def goto(self, url: str, wait_until: str, timeout: int):
            return None

        async def wait_for_timeout(self, ms: int):
            return None

        async def title(self) -> str:
            return "Channel page"

        def locator(self, selector: str):
            return _FakeBody()

        async def content(self) -> str:
            return "<html></html>"

        async def close(self) -> None:
            return None

    class _FakeBrowser:
        def __init__(self) -> None:
            self.new_page_kwargs = None

        async def new_page(self, **kwargs):
            self.new_page_kwargs = kwargs
            return _FakePage()

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

    asyncio.run(runner._fetch_items(SimpleNamespace(entry_url="https://www.youtube.com/@ElectronicArts"), "videos"))

    assert browser.new_page_kwargs["ignore_https_errors"] is True


def test_youtube_runner_raises_for_5xx_error_page(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightYouTubeRunner()

    class _FakeBody:
        async def inner_text(self) -> str:
            return "5xx Server Error"

    class _FakePage:
        async def goto(self, url: str, wait_until: str, timeout: int):
            return None

        async def wait_for_timeout(self, ms: int):
            return None

        async def title(self) -> str:
            return "5xx Server Error"

        def locator(self, selector: str):
            return _FakeBody()

        async def content(self) -> str:
            return "<html><body>5xx Server Error</body></html>"

        async def close(self) -> None:
            return None

    class _FakeBrowser:
        async def new_page(self, **kwargs):
            return _FakePage()

        async def close(self) -> None:
            return None

    class _FakeChromium:
        async def launch(self, headless: bool = True):
            return _FakeBrowser()

    class _FakePlaywrightContext:
        async def __aenter__(self):
            return SimpleNamespace(chromium=_FakeChromium())

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_module = ModuleType("playwright.async_api")
    fake_module.async_playwright = lambda: _FakePlaywrightContext()
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_module)

    with pytest.raises(RuntimeError, match="5xx Server Error"):
        asyncio.run(runner._fetch_items(SimpleNamespace(entry_url="https://www.youtube.com/@ElectronicArts"), "videos"))

def test_extract_youtube_items_supports_traditional_chinese_relative_time() -> None:
    html = """
    <ytd-rich-item-renderer>
      <a id="video-title" href="/watch?v=zhrel" title="中文時間影片">中文時間影片</a>
      <div id="metadata-line">
        <span>收看次數：461K 次</span>
        <span>5 個月前</span>
      </div>
    </ytd-rich-item-renderer>
    """

    items = _extract_youtube_items(html, "videos")

    assert items[0]["published_at"] == "5 個月前"


def test_youtube_strategy_accepts_traditional_chinese_relative_time() -> None:
    runner = _FakeYouTubeRunner(
        {
            "videos": [
                {
                    "title": "中文時間影片",
                    "url": "https://youtube.com/watch?v=zhrel",
                    "published_at": "5 個月前",
                }
            ],
            "shorts": [],
            "streams": [],
        }
    )
    strategy = YouTubeChannelRecentStrategy(runner=runner, today=date(2026, 3, 25))

    items = strategy.execute(SimpleNamespace(entry_url="https://www.youtube.com/@ElectronicArts", max_items=10))

    assert [item["url"] for item in items] == ["https://youtube.com/watch?v=zhrel"]


def test_youtube_runner_uses_domcontentloaded_navigation(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightYouTubeRunner()

    class _FakeBody:
        async def inner_text(self) -> str:
            return "Channel page"

    class _FakePage:
        def __init__(self) -> None:
            self.goto_wait_until = None

        async def goto(self, url: str, wait_until: str, timeout: int):
            self.goto_wait_until = wait_until
            return None

        async def wait_for_timeout(self, ms: int):
            return None

        async def title(self) -> str:
            return "Channel page"

        def locator(self, selector: str):
            return _FakeBody()

        async def content(self) -> str:
            return "<html></html>"

        async def close(self) -> None:
            return None

    class _FakeBrowser:
        def __init__(self) -> None:
            self.page = _FakePage()

        async def new_page(self, **kwargs):
            return self.page

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

    asyncio.run(runner._fetch_items(SimpleNamespace(entry_url="https://www.youtube.com/@ElectronicArts"), "videos"))

    assert browser.page.goto_wait_until == "domcontentloaded"


def test_youtube_runner_uses_partial_content_when_goto_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightYouTubeRunner()

    class _FakeTimeoutError(Exception):
        pass

    class _FakeBody:
        async def inner_text(self) -> str:
            return "Channel page"

    class _FakePage:
        async def goto(self, url: str, wait_until: str, timeout: int):
            raise _FakeTimeoutError("Page.goto timeout")

        async def wait_for_timeout(self, ms: int):
            return None

        async def title(self) -> str:
            return "Channel page"

        def locator(self, selector: str):
            return _FakeBody()

        async def content(self) -> str:
            return """
            <html>
              <body>
                <ytd-rich-item-renderer>
                  <a id="video-title" href="/watch?v=timeout-ok" title="超时后仍可解析">超时后仍可解析</a>
                  <div id="metadata-line">
                    <span>2 days ago</span>
                  </div>
                </ytd-rich-item-renderer>
              </body>
            </html>
            """

        async def close(self) -> None:
            return None

    class _FakeBrowser:
        async def new_page(self, **kwargs):
            return _FakePage()

        async def close(self) -> None:
            return None

    class _FakeChromium:
        async def launch(self, headless: bool = True):
            return _FakeBrowser()

    class _FakePlaywrightContext:
        async def __aenter__(self):
            return SimpleNamespace(chromium=_FakeChromium())

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_module = ModuleType("playwright.async_api")
    fake_module.async_playwright = lambda: _FakePlaywrightContext()
    fake_module.TimeoutError = _FakeTimeoutError
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_module)

    items = asyncio.run(runner._fetch_items(SimpleNamespace(entry_url="https://www.youtube.com/@ElectronicArts"), "videos"))

    assert [item["url"] for item in items] == ["https://www.youtube.com/watch?v=timeout-ok"]


def test_youtube_runner_retries_with_commit_navigation_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightYouTubeRunner()

    class _FakeTimeoutError(Exception):
        pass

    class _FakeBody:
        async def inner_text(self) -> str:
            return "Channel page"

    class _FakePage:
        def __init__(self) -> None:
            self.goto_calls: list[tuple[str, int]] = []

        async def goto(self, url: str, wait_until: str, timeout: int):
            self.goto_calls.append((wait_until, timeout))
            if wait_until == "domcontentloaded":
                raise _FakeTimeoutError("Page.goto timeout")
            return None

        async def wait_for_timeout(self, ms: int):
            return None

        async def title(self) -> str:
            return "Channel page"

        def locator(self, selector: str):
            return _FakeBody()

        async def content(self) -> str:
            wait_modes = [wait_until for wait_until, _ in self.goto_calls]
            if "commit" not in wait_modes:
                return "<html><body></body></html>"
            return """
            <html>
              <body>
                <ytd-rich-item-renderer>
                  <a id="video-title" href="/watch?v=retry-ok" title="重试后成功">重试后成功</a>
                  <div id="metadata-line">
                    <span>1 day ago</span>
                  </div>
                </ytd-rich-item-renderer>
              </body>
            </html>
            """

        async def close(self) -> None:
            return None

    class _FakeBrowser:
        def __init__(self) -> None:
            self.page = _FakePage()

        async def new_page(self, **kwargs):
            return self.page

        async def close(self) -> None:
            return None

    class _FakeChromium:
        def __init__(self, browser: _FakeBrowser) -> None:
            self.browser = browser

        async def launch(self, headless: bool = True):
            return self.browser

    class _FakePlaywrightContext:
        def __init__(self, browser: _FakeBrowser) -> None:
            self.browser = browser

        async def __aenter__(self):
            return SimpleNamespace(chromium=_FakeChromium(self.browser))

        async def __aexit__(self, exc_type, exc, tb):
            return False

    browser = _FakeBrowser()
    fake_module = ModuleType("playwright.async_api")
    fake_module.async_playwright = lambda: _FakePlaywrightContext(browser)
    fake_module.TimeoutError = _FakeTimeoutError
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_module)

    items = asyncio.run(runner._fetch_items(SimpleNamespace(entry_url="https://www.youtube.com/@ElectronicArts"), "videos"))

    assert [item["url"] for item in items] == ["https://www.youtube.com/watch?v=retry-ok"]
    assert browser.page.goto_calls == [("domcontentloaded", 60000), ("commit", 20000)]

def test_youtube_runner_raises_invalid_source_url_for_404_page(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightYouTubeRunner()

    class _FakeBody:
        async def inner_text(self) -> str:
            return ""

    class _FakePage:
        async def goto(self, url: str, wait_until: str, timeout: int):
            return None

        async def wait_for_timeout(self, ms: int):
            return None

        async def title(self) -> str:
            return "404 Not Found"

        def locator(self, selector: str):
            return _FakeBody()

        async def content(self) -> str:
            return "<html><body></body></html>"

        async def close(self) -> None:
            return None

    class _FakeBrowser:
        async def new_page(self, **kwargs):
            return _FakePage()

        async def close(self) -> None:
            return None

    class _FakeChromium:
        async def launch(self, headless: bool = True):
            return _FakeBrowser()

    class _FakePlaywrightContext:
        async def __aenter__(self):
            return SimpleNamespace(chromium=_FakeChromium())

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_module = ModuleType("playwright.async_api")
    fake_module.async_playwright = lambda: _FakePlaywrightContext()
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_module)

    with pytest.raises(RuntimeError, match="来源 URL 无效"):
        asyncio.run(runner._fetch_items(SimpleNamespace(entry_url="https://www.youtube.com/@MissingChannel"), "videos"))
