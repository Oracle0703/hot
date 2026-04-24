from pathlib import Path
from types import SimpleNamespace

from app.collectors.parsers.generic_css_parser import GenericCssParser


FIXTURE_PATH = Path("tests/fixtures/sample_list_page.html")


def test_generic_css_parser_extracts_title_link_and_time() -> None:
    """TC-STRAT-101"""
    parser = GenericCssParser()
    source = SimpleNamespace(
        list_selector=".topic",
        title_selector=".topic-link",
        link_selector=".topic-link",
        meta_selector=".topic-time",
        include_keywords=[],
        exclude_keywords=[],
        max_items=10,
    )

    items = parser.parse(source, FIXTURE_PATH.read_text(encoding="utf-8"))

    assert len(items) == 2
    assert items[0]["title"] == "重磅新游版号过审"
    assert items[0]["url"] == "https://example.com/post-1"
    assert items[0]["published_at"] == "2026-03-24 08:00"


def test_generic_css_parser_keeps_only_matching_keywords() -> None:
    """TC-STRAT-103"""
    parser = GenericCssParser()
    source = SimpleNamespace(
        list_selector=".topic",
        title_selector=".topic-link",
        link_selector=".topic-link",
        meta_selector=".topic-time",
        include_keywords=["新游", "版号"],
        exclude_keywords=["水贴"],
        max_items=10,
    )

    items = parser.parse(source, FIXTURE_PATH.read_text(encoding="utf-8"))

    assert len(items) == 1
    assert items[0]["title"] == "重磅新游版号过审"


def test_generic_css_parser_honors_max_items() -> None:
    """TC-STRAT-104"""
    parser = GenericCssParser()
    source = SimpleNamespace(
        list_selector=".topic",
        title_selector=".topic-link",
        link_selector=".topic-link",
        meta_selector=".topic-time",
        include_keywords=[],
        exclude_keywords=[],
        max_items=1,
    )

    items = parser.parse(source, FIXTURE_PATH.read_text(encoding="utf-8"))

    assert len(items) == 1


def test_generic_css_parser_deduplicates_duplicate_urls() -> None:
    """TC-STRAT-105"""
    parser = GenericCssParser()
    source = SimpleNamespace(
        list_selector=".topic",
        title_selector=".topic-link",
        link_selector=".topic-link",
        meta_selector=".topic-time",
        include_keywords=[],
        exclude_keywords=[],
        max_items=10,
    )
    html = """
    <div class="topic"><a class="topic-link" href="https://example.com/post-1">A</a><span class="topic-time">2026-03-24</span></div>
    <div class="topic"><a class="topic-link" href="https://example.com/post-1">A2</a><span class="topic-time">2026-03-25</span></div>
    """

    items = parser.parse(source, html)

    assert len(items) == 1
    assert items[0]["url"] == "https://example.com/post-1"
