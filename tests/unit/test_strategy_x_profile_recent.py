import asyncio
import os
import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.services.strategies.x_profile_recent import (
    XProfileRecentStrategy,
    _PlaywrightXRunner,
    _extract_x_items,
    _normalize_x_entry_url,
)


class _FakeXRunner:
    def __init__(self, items) -> None:
        self.items = items
        self.requested_sources = []

    def fetch_items(self, source):
        self.requested_sources.append(source)
        return list(self.items)


def test_x_strategy_trims_to_max_items() -> None:
    runner = _FakeXRunner(
        [
            {"title": "post-1", "url": "https://x.com/PUBG/status/1", "published_at": "2026-03-29T09:00:08.000Z"},
            {"title": "post-2", "url": "https://x.com/PUBG/status/2", "published_at": "2026-03-29T08:00:08.000Z"},
            {"title": "post-3", "url": "https://x.com/PUBG/status/3", "published_at": "2026-03-29T07:00:08.000Z"},
        ]
    )
    strategy = XProfileRecentStrategy(runner=runner)
    source = SimpleNamespace(entry_url='https://x.com/PUBG', max_items=2)

    items = strategy.execute(source)

    assert runner.requested_sources == [source]
    assert [item['url'] for item in items] == [
        'https://x.com/PUBG/status/1',
        'https://x.com/PUBG/status/2',
    ]


def test_extract_x_items_reads_visible_tweet_text_and_status_links() -> None:
    html = """
    <html><body>
      <article data-testid="tweet">
        <a href="/PUBG/status/2038179386818441554"><time datetime="2026-03-29T09:00:08.000Z"></time></a>
        <div data-testid="tweetText">Alien army invasion on an alternate Miramar.</div>
      </article>
      <article data-testid="tweet">
        <a href="/PUBG/status/2037915288763511245"><time datetime="2026-03-28T15:30:42.000Z"></time></a>
        <div data-testid="tweetText">Happy 9th Anniversary, PUBG!</div>
      </article>
    </body></html>
    """

    items = _extract_x_items(html, 'https://x.com/PUBG')

    assert [item['url'] for item in items] == [
        'https://x.com/PUBG/status/2038179386818441554',
        'https://x.com/PUBG/status/2037915288763511245',
    ]
    assert items[0]['title'] == 'Alien army invasion on an alternate Miramar.'
    assert items[0]['published_at'] == '2026-03-29T09:00:08.000Z'



def test_normalize_x_entry_url_fixes_common_scheme_typo() -> None:
    assert _normalize_x_entry_url('htps:/x.com/PlayApex') == 'https://x.com/PlayApex'


def test_normalize_x_entry_url_rejects_invalid_host() -> None:
    with pytest.raises(ValueError, match='x.com'):
        _normalize_x_entry_url('https://example.com/PlayApex')
def test_x_runner_adds_required_cookies_to_context(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightXRunner()
    monkeypatch.setenv('X_AUTH_TOKEN', 'token-value')
    monkeypatch.setenv('X_CT0', 'ct0-value')

    class _FakePage:
        async def goto(self, url: str, wait_until: str, timeout: int):
            return None

        async def wait_for_timeout(self, ms: int):
            return None

        async def title(self) -> str:
            return 'Profile / X'

        def locator(self, selector: str):
            class _Body:
                async def inner_text(self) -> str:
                    return 'PUBG: BATTLEGROUNDS @PUBG Official account'
            return _Body()

        async def content(self) -> str:
            return '<html></html>'

        async def close(self) -> None:
            return None

    class _FakeContext:
        def __init__(self) -> None:
            self.cookies = None

        async def add_cookies(self, cookies):
            self.cookies = cookies

        async def new_page(self):
            return _FakePage()

    class _FakeBrowser:
        def __init__(self) -> None:
            self.context = _FakeContext()
            self.new_context_kwargs = None

        async def new_context(self, **kwargs):
            self.new_context_kwargs = kwargs
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

    fake_module = ModuleType('playwright.async_api')
    fake_module.async_playwright = fake_async_playwright
    monkeypatch.setitem(sys.modules, 'playwright.async_api', fake_module)

    asyncio.run(runner._fetch_items(SimpleNamespace(entry_url='https://x.com/PUBG')))

    assert browser.new_context_kwargs['ignore_https_errors'] is True
    cookie_names = {cookie['name'] for cookie in browser.context.cookies}
    assert cookie_names == {'auth_token', 'ct0'}



def test_x_runner_reads_cookies_from_runtime_env_file(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightXRunner()
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    monkeypatch.delenv('X_AUTH_TOKEN', raising=False)
    monkeypatch.delenv('X_CT0', raising=False)

    env_file = tmp_path / 'data' / 'app.env'
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        'X_AUTH_TOKEN=file-token\n'
        'X_CT0=file-ct0\n',
        encoding='utf-8-sig',
    )

    class _FakePage:
        async def goto(self, url: str, wait_until: str, timeout: int):
            return None

        async def wait_for_timeout(self, ms: int):
            return None

        async def title(self) -> str:
            return 'Profile / X'

        def locator(self, selector: str):
            class _Body:
                async def inner_text(self) -> str:
                    return 'PUBG: BATTLEGROUNDS @PUBG Official account'
            return _Body()

        async def content(self) -> str:
            return '<html></html>'

        async def close(self) -> None:
            return None

    class _FakeContext:
        def __init__(self) -> None:
            self.cookies = None

        async def add_cookies(self, cookies):
            self.cookies = cookies

        async def new_page(self):
            return _FakePage()

    class _FakeBrowser:
        def __init__(self) -> None:
            self.context = _FakeContext()
            self.new_context_kwargs = None

        async def new_context(self, **kwargs):
            self.new_context_kwargs = kwargs
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

    fake_module = ModuleType('playwright.async_api')
    fake_module.async_playwright = fake_async_playwright
    monkeypatch.setitem(sys.modules, 'playwright.async_api', fake_module)

    asyncio.run(runner._fetch_items(SimpleNamespace(entry_url='https://x.com/PUBG')))

    assert browser.new_context_kwargs['ignore_https_errors'] is True
    assert {cookie['name'] for cookie in browser.context.cookies} == {'auth_token', 'ct0'}
    assert {cookie['value'] for cookie in browser.context.cookies} == {'file-token', 'file-ct0'}
def test_x_runner_raises_when_cookies_are_missing(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightXRunner()
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    monkeypatch.delenv('X_AUTH_TOKEN', raising=False)
    monkeypatch.delenv('X_CT0', raising=False)

    with pytest.raises(RuntimeError, match='X_AUTH_TOKEN'):
        asyncio.run(runner._fetch_items(SimpleNamespace(entry_url='https://x.com/PUBG')))






