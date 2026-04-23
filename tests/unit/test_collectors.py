import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

from app.collectors.http_collector import HttpCollector
from app.collectors.parsers.generic_css_parser import GenericCssParser
from app.collectors.playwright_collector import PlaywrightCollector
from app.collectors.registry import CollectorRegistry


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = b"<html><body><h1>ok</h1></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A003
        return


def test_http_collector_fetches_html_from_url() -> None:
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        source = SimpleNamespace(entry_url=f"http://127.0.0.1:{server.server_port}/topics")
        html = asyncio.run(HttpCollector().fetch(source))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)

    assert "<h1>ok</h1>" in html


def test_collector_registry_returns_http_collector_and_generic_parser() -> None:
    registry = CollectorRegistry()
    source = SimpleNamespace(fetch_mode="http", parser_type="generic_css")

    collector = registry.get_collector(source)
    parser = registry.get_parser(source)

    assert isinstance(collector, HttpCollector)
    assert isinstance(parser, GenericCssParser)


def test_collector_registry_returns_playwright_collector_for_playwright_mode() -> None:
    registry = CollectorRegistry()
    source = SimpleNamespace(fetch_mode="playwright", parser_type="generic_css")

    collector = registry.get_collector(source)

    assert isinstance(collector, PlaywrightCollector)
