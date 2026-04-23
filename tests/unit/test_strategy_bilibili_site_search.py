import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

from app.services.strategies.bilibili_site_search import (
    BilibiliSiteSearchStrategy,
    _extract_bilibili_items,
    _PlaywrightBilibiliRunner,
)


class _FakeBilibiliRunner:
    def __init__(self, items) -> None:
        self.items = items
        self.queries: list[str] = []

    def search(self, source, query: str):
        self.queries.append(query)
        return list(self.items)


def test_bilibili_strategy_builds_query_with_today_and_limits_to_30_items() -> None:
    runner = _FakeBilibiliRunner(
        [
            {
                "title": f"游戏热点 {index}",
                "url": f"https://www.bilibili.com/video/BV{index:02d}",
                "published_at": f"2026-03-{(index % 9) + 1:02d}",
            }
            for index in range(35)
        ]
    )
    strategy = BilibiliSiteSearchStrategy(runner=runner, today=date(2026, 3, 25))
    source = SimpleNamespace(entry_url="https://www.bilibili.com/", search_keyword="游戏", max_items=100)

    items = strategy.execute(source)

    assert runner.queries == ["游戏 2026-03-25"]
    assert len(items) == 30
    assert items[0]["title"] == "游戏热点 0"
    assert items[-1]["title"] == "游戏热点 29"


def test_bilibili_strategy_requires_search_keyword() -> None:
    strategy = BilibiliSiteSearchStrategy(runner=_FakeBilibiliRunner([]), today=date(2026, 3, 25))
    source = SimpleNamespace(entry_url="https://www.bilibili.com/", search_keyword="   ")

    with pytest.raises(ValueError, match="bilibili search keyword is required"):
        strategy.execute(source)


def test_bilibili_strategy_accepts_entry_url_without_trailing_slash() -> None:
    runner = _FakeBilibiliRunner([])
    strategy = BilibiliSiteSearchStrategy(runner=runner, today=date(2026, 3, 25))
    source = SimpleNamespace(entry_url="https://www.bilibili.com", search_keyword="游戏", max_items=30)

    items = strategy.execute(source)

    assert items == []
    assert runner.queries == ["游戏 2026-03-25"]


def test_bilibili_strategy_accepts_homepage_url_with_query() -> None:
    runner = _FakeBilibiliRunner([])
    strategy = BilibiliSiteSearchStrategy(runner=runner, today=date(2026, 3, 25))
    source = SimpleNamespace(entry_url="https://www.bilibili.com/?from=nav", search_keyword="游戏", max_items=30)

    items = strategy.execute(source)

    assert items == []
    assert runner.queries == ["游戏 2026-03-25"]


@pytest.mark.parametrize("max_items", [0, -1])
def test_bilibili_strategy_returns_empty_when_max_items_is_not_positive(max_items: int) -> None:
    runner = _FakeBilibiliRunner(
        [{"title": "游戏热点", "url": "https://www.bilibili.com/video/BV00", "published_at": "2026-03-01"}]
    )
    strategy = BilibiliSiteSearchStrategy(runner=runner, today=date(2026, 3, 25))
    source = SimpleNamespace(entry_url="https://www.bilibili.com/", search_keyword="游戏", max_items=max_items)

    items = strategy.execute(source)

    assert items == []


def test_extract_bilibili_items_does_not_use_duration_as_published_at() -> None:
    html = """
    <div class="bili-video-card">
      <a href="/video/BV1" title="测试视频">测试视频</a>
      <span class="bili-video-card__stats__duration">12:34</span>
    </div>
    """

    items = _extract_bilibili_items(html)

    assert items[0]["published_at"] is None


def test_extract_bilibili_items_prefers_real_title_anchor_over_overlay_text() -> None:
    html = """
    <div class="bili-video-card">
      <a href="/video/BV1REAL" class="bili-video-card__wrap">
        <span>稍后再看</span>
        <span>433100</span>
        <span>4:10:06</span>
      </a>
      <div class="bili-video-card__info">
        <a href="/video/BV1REAL" title="真正的视频标题" class="bili-video-card__info--tit">真正的视频标题</a>
        <span class="bili-video-card__info--date">12小时前</span>
      </div>
    </div>
    """

    items = _extract_bilibili_items(html)

    assert items[0]["title"] == "真正的视频标题"
    assert items[0]["url"] == "https://www.bilibili.com/video/BV1REAL"
    assert items[0]["published_at"] == "12小时前"

def test_bilibili_runner_search_can_run_inside_running_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _PlaywrightBilibiliRunner()

    async def fake_search(query: str):
        return [{"title": "loop", "url": "https://www.bilibili.com/video/BVLOOP", "published_at": "2026-03-24"}]

    monkeypatch.setattr(runner, "_search", fake_search)

    async def invoke():
        return runner.search(SimpleNamespace(entry_url="https://www.bilibili.com/"), "游戏 2026-03-25")

    items = asyncio.run(invoke())

    assert items[0]["url"] == "https://www.bilibili.com/video/BVLOOP"

