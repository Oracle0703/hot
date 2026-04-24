from __future__ import annotations

import logging
import re
from datetime import date, datetime
from urllib.parse import quote, urljoin, urlparse

from bs4 import BeautifulSoup

from app.config import get_settings
from app.services.network_access_policy import launch_configured_chromium
from app.services.strategies import run_awaitable_sync


logger = logging.getLogger(__name__)
_DURATION_PATTERN = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
_OVERLAY_TITLE_PATTERN = re.compile(r"^稍后再看(?:\d|[.:万亿kKmM\s])*$")
_RESULT_PATH_KEYWORDS = ("/video/", "/read/cv", "/opus/")
_PERMISSION_DENIED_MARKERS = ("权限不足", "没有权限访问当前页面", "无权限访问当前页面")
_LOGIN_REQUIRED_MARKERS = ("请先登录", "登录后", "扫码登录")


class BilibiliSiteSearchStrategy:
    def __init__(self, runner=None, today=None) -> None:
        self.runner = runner or _PlaywrightBilibiliRunner()
        self.today = today

    def execute(self, source) -> list[dict[str, object]]:
        keyword = str(getattr(source, "search_keyword", "") or "").strip()
        if not keyword:
            raise ValueError("bilibili search keyword is required")

        entry_url = str(getattr(source, "entry_url", "") or "").strip()
        if not _is_supported_entry_url(entry_url):
            raise ValueError("bilibili site search currently only supports https://www.bilibili.com")

        raw_limit = getattr(source, "max_items", 30)
        limit = 30 if raw_limit is None else int(raw_limit)
        if limit <= 0:
            return []
        limit = min(limit, 30)

        today = _resolve_today(self.today)
        query = f"{keyword} {today.isoformat()}"

        items: list[dict[str, object]] = []
        seen_urls: set[str] = set()
        for raw_item in self.runner.search(source, query):
            normalized = _normalize_item(raw_item)
            if normalized is None:
                continue

            url = normalized["url"]
            if url in seen_urls:
                continue

            seen_urls.add(url)
            items.append(normalized)
            if len(items) >= limit:
                break

        return items


class _PlaywrightBilibiliRunner:
    def search(self, source, query: str) -> list[dict[str, object]]:
        return run_awaitable_sync(self._search(query))

    async def _search(self, query: str) -> list[dict[str, object]]:
        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("playwright is not installed") from exc

        search_url = f"https://search.bilibili.com/all?keyword={quote(query)}"
        cookies = _get_optional_bilibili_cookies()
        cookie_names = [cookie["name"] for cookie in cookies]
        logger.info(
            "bilibili search start: query=%s cookie_loaded=%s cookie_names=%s",
            query,
            bool(cookies),
            cookie_names,
        )
        async with async_playwright() as playwright:
            browser = await launch_configured_chromium(playwright.chromium, search_url)
            context = await browser.new_context(ignore_https_errors=True)
            if cookies:
                await context.add_cookies(cookies)
            page = await context.new_page()
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
                html = await page.content()
            finally:
                await page.close()
                await context.close()
                await browser.close()
        _ensure_search_page_accessible(html)
        items = _extract_bilibili_items(html)
        logger.info(
            "bilibili search parsed: query=%s item_count=%s cookie_loaded=%s",
            query,
            len(items),
            bool(cookies),
        )
        return items


def _is_supported_entry_url(entry_url: str) -> bool:
    parsed = urlparse(entry_url)
    return parsed.scheme == "https" and parsed.netloc == "www.bilibili.com" and parsed.path in ("", "/")


def _extract_bilibili_items(html: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = [
        "div.bili-video-card",
        "div.video-list-item",
        "li.video-item",
    ]
    nodes = []
    for selector in selectors:
        nodes.extend(soup.select(selector))

    if not nodes:
        nodes = list(soup.select("a[href*='/video/'], a[href*='/read/cv'], a[href*='/opus/']"))

    items: list[dict[str, object]] = []
    for node in nodes:
        anchor = _select_result_anchor(node)
        if anchor is None:
            continue

        href = (anchor.get("href") or "").strip()
        title = _extract_anchor_title(anchor)
        if not href or not title:
            continue

        published_at = _find_published_at(node)
        excerpt = node.get_text(" ", strip=True) or None
        items.append(
            {
                "title": title,
                "url": urljoin("https://www.bilibili.com", href),
                "published_at": published_at,
                "excerpt": excerpt,
                "raw_payload": {
                    "title": title,
                    "url": href,
                    "published_at": published_at,
                },
            }
        )
    return items


def _get_optional_bilibili_cookies() -> list[dict[str, object]]:
    cookie_value = get_settings().bilibili_cookie.strip()
    if not cookie_value:
        return []

    cookies: list[dict[str, object]] = []
    for segment in cookie_value.split(";"):
        chunk = segment.strip()
        if not chunk or "=" not in chunk:
            continue
        name, value = chunk.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name or not value:
            continue
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": ".bilibili.com",
                "path": "/",
                "secure": True,
                "httpOnly": False,
                "sameSite": "Lax",
            }
        )
    return cookies


def _ensure_search_page_accessible(html: str) -> None:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    if any(marker in text for marker in _LOGIN_REQUIRED_MARKERS):
        raise RuntimeError("bilibili search page requires login; please refresh BILIBILI_COOKIE")
    if any(marker in text for marker in _PERMISSION_DENIED_MARKERS):
        raise RuntimeError("bilibili search page returned permission denied; please refresh BILIBILI_COOKIE")


def _select_result_anchor(node):
    if getattr(node, "name", None) == "a":
        return node if _is_supported_result_href(node.get("href")) else None

    candidate_selectors = [
        "a.bili-video-card__info--tit[href]",
        "a[class*='title'][href]",
        "h3 a[href]",
        "a[title][href]",
        "a[href]",
    ]
    seen_ids: set[int] = set()
    for selector in candidate_selectors:
        for anchor in node.select(selector):
            if id(anchor) in seen_ids:
                continue
            seen_ids.add(id(anchor))
            if not _is_supported_result_href(anchor.get("href")):
                continue
            title = _extract_anchor_title(anchor)
            if title:
                return anchor
    return None


def _is_supported_result_href(href: str | None) -> bool:
    value = str(href or "").strip()
    return any(keyword in value for keyword in _RESULT_PATH_KEYWORDS)


def _extract_anchor_title(anchor) -> str:
    title = str(anchor.get("title") or anchor.get("aria-label") or "").strip()
    if title and not _looks_like_overlay_title(title):
        return title

    text = anchor.get_text(" ", strip=True)
    if text and not _looks_like_overlay_title(text) and not _looks_like_duration(text):
        return text
    return ""


def _looks_like_overlay_title(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    return _OVERLAY_TITLE_PATTERN.fullmatch(compact) is not None


def _find_published_at(node) -> str | None:
    selectors = [
        ".bili-video-card__info--date",
        ".time",
        ".so-imgTag_rb",
        ".bili-video-card__info--bottom .bili-video-card__info--date",
    ]
    for selector in selectors:
        candidate = node.select_one(selector)
        if candidate is None:
            continue
        text = candidate.get_text(" ", strip=True)
        if text and not _looks_like_duration(text):
            return text
    return None


def _looks_like_duration(text: str) -> bool:
    return _DURATION_PATTERN.fullmatch(text.strip()) is not None


def _normalize_item(item: dict[str, object]) -> dict[str, object] | None:
    title = str(item.get("title") or "").strip()
    url = str(item.get("url") or "").strip()
    if not title or not url:
        return None

    normalized: dict[str, object] = {
        "title": title,
        "url": url,
        "published_at": item.get("published_at"),
        "raw_payload": dict(item.get("raw_payload") or item),
    }
    excerpt = item.get("excerpt")
    if excerpt:
        normalized["excerpt"] = excerpt
    return normalized


def _resolve_today(value) -> date:
    if callable(value):
        value = value()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.today()



