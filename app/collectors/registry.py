from __future__ import annotations

from app.collectors.http_collector import HttpCollector
from app.collectors.parsers.generic_css_parser import GenericCssParser
from app.collectors.playwright_collector import PlaywrightCollector


class CollectorRegistry:
    def get_collector(self, source):
        if source.fetch_mode == "playwright":
            return PlaywrightCollector()
        return HttpCollector()

    def get_parser(self, source):
        if source.parser_type == "generic_css" or source.parser_type is None:
            return GenericCssParser()
        raise ValueError(f"unsupported parser type: {source.parser_type}")
