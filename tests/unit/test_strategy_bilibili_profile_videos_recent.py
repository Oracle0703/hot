import asyncio
import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.services.strategies.bilibili_profile_videos_recent import (
    BilibiliProfileVideosRecentStrategy,
    _PlaywrightBilibiliProfileRunner,
    _extract_bilibili_profile_video_items,
    _extract_items_from_api_payload,
)


class _FakeBilibiliProfileRunner:
    def __init__(self, items) -> None:
        self.items = items
        self.requested_sources = []

    def fetch_items(self, source):
        self.requested_sources.append(source)
        return list(self.items)


def test_bilibili_profile_strategy_accepts_space_url_with_query() -> None:
    runner = _FakeBilibiliProfileRunner([])
    strategy = BilibiliProfileVideosRecentStrategy(runner=runner)
    source = SimpleNamespace(
        entry_url="https://space.bilibili.com/20411266?spm_id_from=333.1387.follow.user_card.click",
        max_items=10,
    )

    items = strategy.execute(source)

    assert items == []
    assert runner.requested_sources == [source]


def test_bilibili_profile_strategy_rejects_non_space_url() -> None:
    strategy = BilibiliProfileVideosRecentStrategy(runner=_FakeBilibiliProfileRunner([]))
    source = SimpleNamespace(entry_url="https://www.bilibili.com/", max_items=10)

    with pytest.raises(ValueError, match="space.bilibili.com"):
        strategy.execute(source)


def test_bilibili_profile_strategy_deduplicates_and_limits_items() -> None:
    runner = _FakeBilibiliProfileRunner(
        [
            {"title": "?? 1", "url": "https://www.bilibili.com/video/BV1", "published_at": "2026-03-30"},
            {"title": "?? 1 ??", "url": "https://www.bilibili.com/video/BV1", "published_at": "2026-03-30"},
            {"title": "?? 2", "url": "https://www.bilibili.com/video/BV2", "published_at": "2026-03-29"},
        ]
    )
    strategy = BilibiliProfileVideosRecentStrategy(runner=runner)
    source = SimpleNamespace(entry_url="https://space.bilibili.com/20411266", max_items=2)

    items = strategy.execute(source)

    assert [item["url"] for item in items] == [
        "https://www.bilibili.com/video/BV1",
        "https://www.bilibili.com/video/BV2",
    ]


def test_bilibili_profile_strategy_enriches_items_with_bilibili_stats() -> None:
    runner = _FakeBilibiliProfileRunner(
        [
            {"title": "视频1", "url": "https://www.bilibili.com/video/BV1STAT", "published_at": "2026-04-22"},
        ]
    )
    strategy = BilibiliProfileVideosRecentStrategy(
        runner=runner,
        detail_fetcher=lambda url: {
            "like_count": 3689,
            "reply_count": 206,
            "view_count": 61317,
            "cover_image_url": "https://i0.hdslb.com/demo.jpg",
        },
    )

    items = strategy.execute(SimpleNamespace(entry_url="https://space.bilibili.com/20411266", max_items=1))

    assert items[0]["like_count"] == 3689
    assert items[0]["reply_count"] == 206
    assert items[0]["view_count"] == 61317
    assert items[0]["cover_image_url"] == "https://i0.hdslb.com/demo.jpg"


def test_bilibili_profile_strategy_retries_once_when_redirect_or_risk_control_is_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('BILIBILI_RETRY_DELAY_SECONDS', raising=False)

    class _RetryableRunner:
        def __init__(self) -> None:
            self.call_count = 0

        def fetch_items(self, source):
            self.call_count += 1
            if self.call_count == 1:
                raise RuntimeError(
                    "bilibili profile page redirected to unexpected url (可能触发风控或登录失效): "
                    "https://member.bilibili.com/platform/upload/video/frame"
                )
            return [{"title": "重试后视频", "url": "https://www.bilibili.com/video/BVRETRY", "published_at": "2026-04-01"}]

    sleep_calls: list[float] = []
    runner = _RetryableRunner()
    strategy = BilibiliProfileVideosRecentStrategy(
        runner=runner,
        sleeper=lambda seconds: sleep_calls.append(seconds),
    )
    source = SimpleNamespace(entry_url="https://space.bilibili.com/20411266", max_items=1)

    items = strategy.execute(source)

    assert runner.call_count == 2
    assert sleep_calls == [5.0]
    assert [item["url"] for item in items] == ["https://www.bilibili.com/video/BVRETRY"]


def test_bilibili_profile_strategy_uses_configured_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('BILIBILI_RETRY_DELAY_SECONDS', '9')

    class _RetryableRunner:
        def __init__(self) -> None:
            self.call_count = 0

        def fetch_items(self, source):
            self.call_count += 1
            if self.call_count == 1:
                raise RuntimeError("bilibili profile page hit risk control (风控); 请稍后重试或刷新 BILIBILI_COOKIE")
            return [{"title": "重试后视频", "url": "https://www.bilibili.com/video/BVRETRY2", "published_at": "2026-04-01"}]

    sleep_calls: list[float] = []
    strategy = BilibiliProfileVideosRecentStrategy(
        runner=_RetryableRunner(),
        sleeper=lambda seconds: sleep_calls.append(seconds),
    )

    items = strategy.execute(SimpleNamespace(entry_url="https://space.bilibili.com/20411266", max_items=1))

    assert sleep_calls == [9.0]
    assert [item["url"] for item in items] == ["https://www.bilibili.com/video/BVRETRY2"]


def test_extract_bilibili_profile_video_items_prefers_detail_title_and_subtitle_date() -> None:
    html = """
    <div class="upload-video-card grid-mode">
      <div class="bili-video-card">
        <div class="bili-video-card__wrap">
          <div class="bili-video-card__cover">
            <a class="bili-cover-card" href="//www.bilibili.com/video/BV1REAL" target="_blank">
              <div class="bili-cover-card__stats">
                <div class="bili-cover-card__stat"><span>1.9?</span></div>
                <div class="bili-cover-card__stat"><span>21</span></div>
                <div class="bili-cover-card__stat"><span>03:10</span></div>
              </div>
            </a>
          </div>
          <div class="bili-video-card__details">
            <div class="bili-video-card__title" title="real title text">
              <a href="//www.bilibili.com/video/BV1REAL" target="_blank">real title text</a>
            </div>
            <div class="bili-video-card__subtitle"><span>03-24</span></div>
          </div>
        </div>
      </div>
    </div>
    """

    items = _extract_bilibili_profile_video_items(html)

    assert len(items) == 1
    assert items[0]["title"] == "real title text"
    assert items[0]["url"] == "https://www.bilibili.com/video/BV1REAL"
    assert items[0]["published_at"] == "03-24"


def test_extract_bilibili_profile_video_items_reads_video_cards() -> None:
    html = """
    <div class="list-item">
      <a class="cover" href="//www.bilibili.com/video/BV1REAL"></a>
      <a class="title" href="//www.bilibili.com/video/BV1REAL" title="???????">???????</a>
      <div class="meta">
        <span class="time">2026-03-29</span>
      </div>
    </div>
    <div class="list-item">
      <a class="title" href="https://www.bilibili.com/read/cv123" title="??">??</a>
      <span class="time">2026-03-28</span>
    </div>
    """

    items = _extract_bilibili_profile_video_items(html)

    assert len(items) == 1
    assert items[0]["title"] == "???????"
    assert items[0]["url"] == "https://www.bilibili.com/video/BV1REAL"
    assert items[0]["published_at"] == "2026-03-29"


def test_extract_bilibili_profile_video_items_ignores_member_upload_frame_links() -> None:
    html = """
    <div class="list-item">
      <a class="title" href="https://member.bilibili.com/platform/upload/video/frame" title="热点报告更新">热点报告更新</a>
      <div class="meta">
        <span class="time">未知时间</span>
      </div>
    </div>
    """

    items = _extract_bilibili_profile_video_items(html)

    assert items == []


def test_extract_items_from_api_payload_reads_arc_list() -> None:
    payload = {
        "code": 0,
        "data": {
            "list": {
                "vlist": [
                    {
                        "title": "api title",
                        "bvid": "BV1API",
                        "created": 1774819200,
                        "description": "api desc",
                        "author": "真实UP主",
                    }
                ]
            }
        },
    }

    items = _extract_items_from_api_payload(payload)

    assert len(items) == 1
    assert items[0]["title"] == "api title"
    assert items[0]["url"] == "https://www.bilibili.com/video/BV1API"
    assert items[0]["excerpt"] == "api desc"
    assert items[0]["author"] == "真实UP主"


def test_extract_items_from_api_payload_raises_for_risk_control() -> None:
    payload = {"code": -352, "message": "??????", "data": {"v_voucher": "voucher-demo"}}

    with pytest.raises(RuntimeError, match="code=-352"):
        _extract_items_from_api_payload(payload)


def test_bilibili_profile_runner_raises_when_cookie_is_missing(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightBilibiliProfileRunner()
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    monkeypatch.delenv('BILIBILI_COOKIE', raising=False)

    with pytest.raises(RuntimeError, match='BILIBILI_COOKIE'):
        asyncio.run(runner._fetch_items(SimpleNamespace(entry_url='https://space.bilibili.com/20411266')))


def test_bilibili_profile_runner_adds_parsed_cookie_to_context(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightBilibiliProfileRunner()
    monkeypatch.setenv('BILIBILI_COOKIE', 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123')

    class _FakeResponse:
        url = 'https://api.bilibili.com/x/space/wbi/arc/search?mid=20411266'

        async def json(self):
            return {
                'code': 0,
                'data': {'list': {'vlist': [{'title': 'api title', 'bvid': 'BV1API', 'created': 1774819200}]}}
            }

    class _FakePage:
        def __init__(self) -> None:
            self.handlers = {}

        def on(self, event: str, handler):
            self.handlers[event] = handler

        async def goto(self, url: str, wait_until: str, timeout: int):
            await self.handlers['response'](_FakeResponse())
            return None

        async def wait_for_timeout(self, ms: int):
            return None

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

    fake_module = ModuleType('playwright.async_api')
    fake_module.async_playwright = fake_async_playwright
    monkeypatch.setitem(sys.modules, 'playwright.async_api', fake_module)

    items = asyncio.run(runner._fetch_items(SimpleNamespace(entry_url='https://space.bilibili.com/20411266')))

    assert len(items) == 1
    cookie_names = {cookie['name'] for cookie in browser.context.cookies}
    assert cookie_names == {'SESSDATA', 'bili_jct', 'DedeUserID'}
    assert {cookie['domain'] for cookie in browser.context.cookies} == {'.bilibili.com'}




def test_bilibili_profile_runner_raises_when_page_requires_login(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    runner = _PlaywrightBilibiliProfileRunner()
    monkeypatch.setenv('BILIBILI_COOKIE', 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123')

    class _FakePage:
        def on(self, event: str, handler):
            return None

        async def goto(self, url: str, wait_until: str, timeout: int):
            return None

        async def wait_for_timeout(self, ms: int):
            return None

        async def content(self) -> str:
            return '<html><body><h1>请先登录</h1><p>登录后查看更多投稿视频</p></body></html>'

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

    fake_module = ModuleType('playwright.async_api')
    fake_module.async_playwright = fake_async_playwright
    monkeypatch.setitem(sys.modules, 'playwright.async_api', fake_module)

    with caplog.at_level('INFO'):
        with pytest.raises(RuntimeError, match='登录'):
            asyncio.run(runner._fetch_items(SimpleNamespace(entry_url='https://space.bilibili.com/20411266')))

    assert 'cookie_names' in caplog.text


def test_bilibili_profile_runner_raises_when_page_hits_risk_control(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightBilibiliProfileRunner()
    monkeypatch.setenv('BILIBILI_COOKIE', 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123')

    class _FakePage:
        def on(self, event: str, handler):
            return None

        async def goto(self, url: str, wait_until: str, timeout: int):
            return None

        async def wait_for_timeout(self, ms: int):
            return None

        async def content(self) -> str:
            return '<html><body><h1>访问频繁</h1><p>当前访问存在风险，请稍后再试</p></body></html>'

        async def close(self) -> None:
            return None

    class _FakeContext:
        async def add_cookies(self, cookies):
            return None

        async def new_page(self):
            return _FakePage()

        async def close(self) -> None:
            return None

    class _FakeBrowser:
        async def new_context(self, **kwargs):
            return _FakeContext()

        async def close(self) -> None:
            return None

    class _FakeChromium:
        async def launch(self, headless: bool = True):
            return _FakeBrowser()

    class _FakePlaywrightContext:
        def __init__(self) -> None:
            self._playwright = SimpleNamespace(chromium=_FakeChromium())

        async def __aenter__(self):
            return self._playwright

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_module = ModuleType('playwright.async_api')
    fake_module.async_playwright = lambda: _FakePlaywrightContext()
    monkeypatch.setitem(sys.modules, 'playwright.async_api', fake_module)

    with pytest.raises(RuntimeError, match='风控|访问频繁|风险'):
        asyncio.run(runner._fetch_items(SimpleNamespace(entry_url='https://space.bilibili.com/20411266')))


def test_bilibili_profile_runner_raises_when_redirected_to_member_upload_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightBilibiliProfileRunner()
    monkeypatch.setenv('BILIBILI_COOKIE', 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123')

    class _FakePage:
        def __init__(self) -> None:
            self.url = 'https://space.bilibili.com/20411266/video'

        def on(self, event: str, handler):
            return None

        async def goto(self, url: str, wait_until: str, timeout: int):
            self.url = 'https://member.bilibili.com/platform/upload/video/frame'
            return None

        async def wait_for_timeout(self, ms: int):
            return None

        async def content(self) -> str:
            return '<html><body><a href="https://member.bilibili.com/platform/upload/video/frame">热点报告更新</a></body></html>'

        async def close(self) -> None:
            return None

    class _FakeContext:
        async def add_cookies(self, cookies):
            return None

        async def new_page(self):
            return _FakePage()

        async def close(self) -> None:
            return None

    class _FakeBrowser:
        async def new_context(self, **kwargs):
            return _FakeContext()

        async def close(self) -> None:
            return None

    class _FakeChromium:
        async def launch(self, headless: bool = True):
            return _FakeBrowser()

    class _FakePlaywrightContext:
        def __init__(self) -> None:
            self._playwright = SimpleNamespace(chromium=_FakeChromium())

        async def __aenter__(self):
            return self._playwright

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_module = ModuleType('playwright.async_api')
    fake_module.async_playwright = lambda: _FakePlaywrightContext()
    monkeypatch.setitem(sys.modules, 'playwright.async_api', fake_module)

    with pytest.raises(RuntimeError, match='redirected|跳转|member\\.bilibili\\.com'):
        asyncio.run(runner._fetch_items(SimpleNamespace(entry_url='https://space.bilibili.com/20411266')))


def test_bilibili_profile_runner_logs_cookie_names_and_api_code(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    runner = _PlaywrightBilibiliProfileRunner()
    monkeypatch.setenv('BILIBILI_COOKIE', 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123')

    class _FakeResponse:
        url = 'https://api.bilibili.com/x/space/wbi/arc/search?mid=20411266'

        async def json(self):
            return {
                'code': 0,
                'data': {'list': {'vlist': [{'title': 'api title', 'bvid': 'BV1API', 'created': 1774819200}]}}
            }

    class _FakePage:
        def __init__(self) -> None:
            self.handlers = {}

        def on(self, event: str, handler):
            self.handlers[event] = handler

        async def goto(self, url: str, wait_until: str, timeout: int):
            await self.handlers['response'](_FakeResponse())
            return None

        async def wait_for_timeout(self, ms: int):
            return None

        async def content(self) -> str:
            return '<html></html>'

        async def close(self) -> None:
            return None

    class _FakeContext:
        async def add_cookies(self, cookies):
            return None

        async def new_page(self):
            return _FakePage()

        async def close(self) -> None:
            return None

    class _FakeBrowser:
        async def new_context(self, **kwargs):
            return _FakeContext()

        async def close(self) -> None:
            return None

    class _FakeChromium:
        async def launch(self, headless: bool = True):
            return _FakeBrowser()

    class _FakePlaywrightContext:
        def __init__(self) -> None:
            self._playwright = SimpleNamespace(chromium=_FakeChromium())

        async def __aenter__(self):
            return self._playwright

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_module = ModuleType('playwright.async_api')
    fake_module.async_playwright = lambda: _FakePlaywrightContext()
    monkeypatch.setitem(sys.modules, 'playwright.async_api', fake_module)

    with caplog.at_level('INFO'):
        items = asyncio.run(runner._fetch_items(SimpleNamespace(entry_url='https://space.bilibili.com/20411266')))

    assert len(items) == 1
    assert 'SESSDATA' in caplog.text
    assert 'api_code=0' in caplog.text


def test_bilibili_profile_runner_falls_back_to_html_when_api_hits_risk_control(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightBilibiliProfileRunner()
    monkeypatch.setenv('BILIBILI_COOKIE', 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123')

    class _FakeResponse:
        url = 'https://api.bilibili.com/x/space/wbi/arc/search?mid=20411266'

        async def json(self):
            return {'code': -352, 'message': 'risk control'}

    class _FakePage:
        def __init__(self) -> None:
            self.handlers = {}

        def on(self, event: str, handler):
            self.handlers[event] = handler

        async def goto(self, url: str, wait_until: str, timeout: int):
            await self.handlers['response'](_FakeResponse())
            return None

        async def wait_for_timeout(self, ms: int):
            return None

        async def content(self) -> str:
            return """
            <html><body>
              <div class="list-item">
                <a class="title" href="//www.bilibili.com/video/BV1HTML" title="html title">html title</a>
                <span class="time">2026-04-03</span>
              </div>
            </body></html>
            """

        async def close(self) -> None:
            return None

    class _FakeContext:
        async def add_cookies(self, cookies):
            return None

        async def new_page(self):
            return _FakePage()

        async def close(self) -> None:
            return None

    class _FakeBrowser:
        async def new_context(self, **kwargs):
            return _FakeContext()

        async def close(self) -> None:
            return None

    class _FakeChromium:
        async def launch(self, headless: bool = True):
            return _FakeBrowser()

    class _FakePlaywrightContext:
        def __init__(self) -> None:
            self._playwright = SimpleNamespace(chromium=_FakeChromium())

        async def __aenter__(self):
            return self._playwright

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_module = ModuleType('playwright.async_api')
    fake_module.async_playwright = lambda: _FakePlaywrightContext()
    monkeypatch.setitem(sys.modules, 'playwright.async_api', fake_module)

    items = asyncio.run(runner._fetch_items(SimpleNamespace(entry_url='https://space.bilibili.com/20411266')))

    assert len(items) == 1
    assert items[0]['url'] == 'https://www.bilibili.com/video/BV1HTML'


def test_bilibili_profile_runner_prefers_runtime_storage_state_when_present(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightBilibiliProfileRunner()
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    monkeypatch.setenv('BILIBILI_COOKIE', 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123')
    storage_state_file = tmp_path / 'data' / 'bilibili-storage-state.json'
    storage_state_file.parent.mkdir(parents=True, exist_ok=True)
    storage_state_file.write_text('{"cookies":[],"origins":[]}', encoding='utf-8')

    class _FakeResponse:
        url = 'https://api.bilibili.com/x/space/wbi/arc/search?mid=20411266'

        async def json(self):
            return {
                'code': 0,
                'data': {'list': {'vlist': [{'title': 'api title', 'bvid': 'BV1API', 'created': 1774819200}]}}
            }

    class _FakePage:
        def __init__(self) -> None:
            self.handlers = {}

        def on(self, event: str, handler):
            self.handlers[event] = handler

        async def goto(self, url: str, wait_until: str, timeout: int):
            await self.handlers['response'](_FakeResponse())
            return None

        async def wait_for_timeout(self, ms: int):
            return None

        async def content(self) -> str:
            return '<html></html>'

        async def close(self) -> None:
            return None

    class _FakeContext:
        async def add_cookies(self, cookies):
            return None

        async def new_page(self):
            return _FakePage()

        async def close(self) -> None:
            return None

    class _FakeBrowser:
        def __init__(self) -> None:
            self.new_context_kwargs = None

        async def new_context(self, **kwargs):
            self.new_context_kwargs = kwargs
            return _FakeContext()

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
    fake_module = ModuleType('playwright.async_api')
    fake_module.async_playwright = lambda: _FakePlaywrightContext(browser)
    monkeypatch.setitem(sys.modules, 'playwright.async_api', fake_module)

    items = asyncio.run(runner._fetch_items(SimpleNamespace(entry_url='https://space.bilibili.com/20411266')))

    assert len(items) == 1
    assert browser.new_context_kwargs['storage_state'] == str(storage_state_file)
