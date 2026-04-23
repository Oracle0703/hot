from __future__ import annotations

from typing import Protocol


class Collector(Protocol):
    async def fetch(self, source) -> str: ...


class Parser(Protocol):
    def parse(self, source, html: str) -> list[dict[str, object]]: ...
