from __future__ import annotations

from datetime import datetime
import re
from urllib.parse import urlsplit

import httpx

from app.services.network_access_policy import build_httpx_request_kwargs


_BILIBILI_VIDEO_HOSTS = {"www.bilibili.com", "m.bilibili.com"}
_BILIBILI_BVID_RE = re.compile(r"/video/(?P<bvid>BV[0-9A-Za-z]+)(?:[/?#]|$)")


def fetch_bilibili_video_detail_by_url(url: str | None) -> dict[str, object] | None:
    bvid = extract_bilibili_bvid(url)
    if bvid is None:
        return None

    api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True, **build_httpx_request_kwargs(api_url)) as client:
            response = client.get(
                api_url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://www.bilibili.com/",
                },
            )
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return None

    if not isinstance(payload, dict) or int(payload.get("code", -1) or 0) != 0:
        return None

    data = payload.get("data") or {}
    stat = data.get("stat") or {}
    published_at_text = None
    pubdate = data.get("pubdate")
    if pubdate is not None:
        try:
            published_at_text = datetime.fromtimestamp(int(pubdate)).strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError, OSError):
            published_at_text = None

    return {
        "author": _compact_text((data.get("owner") or {}).get("name")),
        "published_at_text": published_at_text,
        "cover_image_url": _compact_text(data.get("pic")),
        "like_count": normalize_count(stat.get("like")),
        "reply_count": normalize_count(stat.get("reply")),
        "view_count": normalize_count(stat.get("view")),
    }


def extract_bilibili_bvid(url: str | None) -> str | None:
    parsed = urlsplit(str(url or "").strip())
    if parsed.scheme != "https" or parsed.netloc.lower() not in _BILIBILI_VIDEO_HOSTS:
        return None
    match = _BILIBILI_BVID_RE.search(parsed.path)
    if match is None:
        return None
    return match.group("bvid")


def normalize_count(value: object) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _compact_text(value: object) -> str | None:
    text = " ".join(str(value or "").split())
    return text or None
