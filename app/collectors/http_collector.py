from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import httpx

from app.services.network_access_policy import build_httpx_request_kwargs


class HttpCollector:
    async def fetch(self, source) -> str:
        parsed = urlparse(source.entry_url)
        if parsed.scheme == "file":
            file_path = Path(url2pathname(unquote(parsed.path)))
            return file_path.read_text(encoding="utf-8")

        request_kwargs = build_httpx_request_kwargs(source.entry_url)
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, **request_kwargs) as client:
            response = await client.get(source.entry_url)
            response.raise_for_status()
            return response.text
