import asyncio
from types import SimpleNamespace

import pytest

from app.collectors.registry import CollectorRegistry
from app.services.source_execution_service import SourceExecutionService


class _FakeCollector:
    def __init__(self, html: str = "<html></html>") -> None:
        self.html = html
        self.received_sources = []

    async def fetch(self, source) -> str:
        self.received_sources.append(source)
        return self.html


class _FakeParser:
    def __init__(self, items) -> None:
        self.items = items
        self.received_sources = []
        self.received_html: list[str] = []

    def parse(self, source, html: str):
        self.received_sources.append(source)
        self.received_html.append(html)
        return self.items


class _FakeRegistry:
    def __init__(self, collector, parser) -> None:
        self.collector = collector
        self.parser = parser

    def get_collector(self, source):
        return self.collector

    def get_parser(self, source):
        return self.parser


class _UnexpectedRegistry:
    def get_collector(self, source):
        raise AssertionError("generic collector chain should not be used")

    def get_parser(self, source):
        raise AssertionError("generic parser chain should not be used")


class _FakeStrategy:
    def __init__(self, items) -> None:
        self.items = items
        self.executed_sources = []

    def execute(self, source):
        self.executed_sources.append(source)
        return self.items


def test_source_execution_service_uses_generic_registry_chain_without_real_http() -> None:
    source = SimpleNamespace(
        entry_url="https://example.com/topics",
        fetch_mode="http",
        parser_type="generic_css",
        include_keywords=["新游", "版号"],
        exclude_keywords=["水贴"],
        max_items=10,
    )
    collector = _FakeCollector("<html><body>fake page</body></html>")
    parser = _FakeParser(
        [{"title": "重磅新游版号过审", "url": "https://example.com/post-1", "published_at": "2026-03-24 08:00"}]
    )
    service = SourceExecutionService(_FakeRegistry(collector, parser))

    result = service.execute(source)

    assert collector.received_sources == [source]
    assert parser.received_sources == [source]
    assert parser.received_html == ["<html><body>fake page</body></html>"]
    assert result["item_count"] == 1
    assert result["items"][0]["title"] == "重磅新游版号过审"


def test_source_execution_service_rejects_generic_parser_returning_none() -> None:
    source = SimpleNamespace(entry_url="https://example.com/topics", fetch_mode="http", parser_type="generic_css")
    service = SourceExecutionService(_FakeRegistry(_FakeCollector(), _FakeParser(None)))

    with pytest.raises(ValueError, match="generic parser must return a list of items"):
        service.execute(source)


def test_source_execution_service_rejects_generic_parser_returning_non_list() -> None:
    source = SimpleNamespace(entry_url="https://example.com/topics", fetch_mode="http", parser_type="generic_css")
    service = SourceExecutionService(_FakeRegistry(_FakeCollector(), _FakeParser({"title": "oops"})))

    with pytest.raises(ValueError, match="generic parser must return a list of items"):
        service.execute(source)


def test_source_execution_service_keeps_generic_chain_for_generic_css_strategy() -> None:
    items = [{"title": "保留旧链路", "url": "https://example.com/a", "published_at": "2026-03-24"}]
    parser = _FakeParser(items)
    source = SimpleNamespace(
        entry_url="https://example.com/topics",
        fetch_mode="http",
        parser_type="generic_css",
        collection_strategy="generic_css",
    )
    service = SourceExecutionService(
        _FakeRegistry(_FakeCollector(), parser),
        strategy_factory=lambda name: (_ for _ in ()).throw(AssertionError("strategy factory should not be called")),
    )

    result = service.execute(source)

    assert result == {"item_count": 1, "items": items}
    assert parser.received_html == ["<html></html>"]


def test_source_execution_service_dispatches_to_non_generic_strategy() -> None:
    strategy = _FakeStrategy(
        [
            {
                "title": "YouTube 更新",
                "url": "https://youtube.com/watch?v=123",
                "published_at": "2026-03-24",
            }
        ]
    )
    seen_strategies: list[str] = []

    def strategy_factory(name: str):
        seen_strategies.append(name)
        return strategy

    source = SimpleNamespace(collection_strategy="youtube_channel_recent")
    service = SourceExecutionService(_UnexpectedRegistry(), strategy_factory=strategy_factory)

    result = service.execute(source)

    assert seen_strategies == ["youtube_channel_recent"]
    assert strategy.executed_sources == [source]
    assert result["item_count"] == 1
    assert result["items"][0]["url"] == "https://youtube.com/watch?v=123"


def test_source_execution_service_dispatches_to_bilibili_profile_video_strategy() -> None:
    strategy = _FakeStrategy(
        [
            {
                "title": "UP????",
                "url": "https://www.bilibili.com/video/BV1TEST",
                "published_at": "2026-03-30",
            }
        ]
    )
    seen_strategies: list[str] = []

    def strategy_factory(name: str):
        seen_strategies.append(name)
        return strategy

    source = SimpleNamespace(collection_strategy="bilibili_profile_videos_recent")
    service = SourceExecutionService(_UnexpectedRegistry(), strategy_factory=strategy_factory)

    result = service.execute(source)

    assert seen_strategies == ["bilibili_profile_videos_recent"]
    assert strategy.executed_sources == [source]
    assert result["item_count"] == 1
    assert result["items"][0]["url"] == "https://www.bilibili.com/video/BV1TEST"


def test_source_execution_service_rejects_strategy_returning_none() -> None:
    source = SimpleNamespace(collection_strategy="youtube_channel_recent")
    service = SourceExecutionService(_UnexpectedRegistry(), strategy_factory=lambda name: _FakeStrategy(None))

    with pytest.raises(ValueError, match="collection strategy youtube_channel_recent must return a list of items"):
        service.execute(source)


def test_source_execution_service_rejects_strategy_returning_non_list() -> None:
    source = SimpleNamespace(collection_strategy="youtube_channel_recent")
    service = SourceExecutionService(
        _UnexpectedRegistry(), strategy_factory=lambda name: _FakeStrategy({"title": "oops"})
    )

    with pytest.raises(ValueError, match="collection strategy youtube_channel_recent must return a list of items"):
        service.execute(source)


def test_source_execution_service_can_run_inside_running_event_loop() -> None:
    source = SimpleNamespace(
        entry_url="https://example.com/topics",
        fetch_mode="http",
        parser_type="generic_css",
        collection_strategy="generic_css",
    )
    collector = _FakeCollector("<html><body>fake page</body></html>")
    parser = _FakeParser(
        [{"title": "事件循环内执行", "url": "https://example.com/post-1", "published_at": "2026-03-24 08:00"}]
    )
    service = SourceExecutionService(_FakeRegistry(collector, parser))

    async def invoke():
        return service.execute(source)

    result = asyncio.run(invoke())

    assert result["item_count"] == 1
    assert result["items"][0]["title"] == "事件循环内执行"


def test_source_execution_service_rejects_unknown_collection_strategy() -> None:
    service = SourceExecutionService(CollectorRegistry())

    with pytest.raises(ValueError, match="unsupported collection strategy: legacy_custom"):
        service.execute(SimpleNamespace(collection_strategy="legacy_custom"))
