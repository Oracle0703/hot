from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.services.network_access_policy import launch_configured_chromium
from app.services.strategies import run_awaitable_sync


_SECTION_NAMES = ("videos", "shorts", "streams")
_YOUTUBE_NAVIGATION_TIMEOUT_MS = 60000
_YOUTUBE_RETRY_TIMEOUT_MS = 20000
_YOUTUBE_POST_NAVIGATION_WAIT_MS = 1500
_RELATIVE_PATTERN = re.compile(r"(?P<value>\d+)\s+(?P<unit>minute|hour|day|week|month|year)s?\s+ago", re.IGNORECASE)
_TRADITIONAL_CHINESE_RELATIVE_PATTERN = re.compile(
    r"(?P<value>\d+)\s*(?P<unit>分鐘|小時|天|週|周|個月|月|年)\s*前"
)
_ENGLISH_DATE_PATTERN = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|January|February|March|April|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b")
_ISO_DATE_PATTERN = re.compile(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b")
_VIEW_PATTERN = re.compile(
    r"\bviews?\b|收看次數|观看次数|觀看次數|收看次数|次觀看|次观看",
    re.IGNORECASE,
)
_ABSOLUTE_PATTERNS = ("%Y-%m-%d", "%Y/%m/%d", "%b %d, %Y", "%B %d, %Y")


class YouTubeChannelRecentStrategy:
    def __init__(self, runner=None, today=None) -> None:
        self.runner = runner or _PlaywrightYouTubeRunner()
        self.today = today

    def execute(self, source) -> list[dict[str, object]]:
        raw_limit = getattr(source, "max_items", 30)
        max_items = 30 if raw_limit is None else int(raw_limit)
        if max_items <= 0:
            return []

        today = _resolve_today(self.today)
        cutoff = today - timedelta(days=365)
        items: list[dict[str, object]] = []
        seen_urls: set[str] = set()

        for section in _SECTION_NAMES:
            for raw_item in self.runner.fetch_items(source, section):
                published_on = _coerce_to_date(raw_item.get("published_at"), today)
                if published_on is None or published_on < cutoff:
                    continue

                normalized = _normalize_item(raw_item, section, published_on)
                if normalized is None:
                    continue

                url = normalized["url"]
                if url in seen_urls:
                    continue

                seen_urls.add(url)
                items.append(normalized)
                if len(items) >= max_items:
                    return items

        return items


class _PlaywrightYouTubeRunner:
    def fetch_items(self, source, section: str) -> list[dict[str, object]]:
        return run_awaitable_sync(self._fetch_items(source, section))

    async def _fetch_items(self, source, section: str) -> list[dict[str, object]]:
        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("playwright is not installed") from exc
        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        except (ImportError, ModuleNotFoundError):  # pragma: no cover - test doubles may omit this export
            PlaywrightTimeoutError = TimeoutError

        target_url = _build_section_url(getattr(source, "entry_url", ""), section)
        async with async_playwright() as playwright:
            browser = await launch_configured_chromium(playwright.chromium, target_url)
            page = await browser.new_page(ignore_https_errors=True)
            try:
                html, navigation_timeout_error = await self._load_html_with_timeout_fallback(
                    page,
                    target_url,
                    section,
                    PlaywrightTimeoutError,
                )
            finally:
                await page.close()
                await browser.close()
        items = _extract_youtube_items(html, section)
        if items:
            return items
        if navigation_timeout_error is not None:
            raise RuntimeError(f"YouTube 页面加载超时: {target_url}") from navigation_timeout_error
        return items

    async def _load_html_with_timeout_fallback(self, page, target_url: str, section: str, timeout_error_type) -> tuple[str, BaseException | None]:
        html, navigation_timeout_error = await self._load_html_once(
            page,
            target_url,
            wait_until="domcontentloaded",
            timeout_ms=_YOUTUBE_NAVIGATION_TIMEOUT_MS,
            timeout_error_type=timeout_error_type,
        )
        if navigation_timeout_error is None or _extract_youtube_items(html, section):
            return html, navigation_timeout_error

        retry_html, retry_timeout_error = await self._load_html_once(
            page,
            target_url,
            wait_until="commit",
            timeout_ms=_YOUTUBE_RETRY_TIMEOUT_MS,
            timeout_error_type=timeout_error_type,
        )
        if retry_timeout_error is None:
            return retry_html, navigation_timeout_error
        return retry_html, retry_timeout_error

    async def _load_html_once(
        self,
        page,
        target_url: str,
        *,
        wait_until: str,
        timeout_ms: int,
        timeout_error_type,
    ) -> tuple[str, BaseException | None]:
        navigation_timeout_error = None
        try:
            await page.goto(target_url, wait_until=wait_until, timeout=timeout_ms)
        except timeout_error_type as exc:
            navigation_timeout_error = exc
        await page.wait_for_timeout(_YOUTUBE_POST_NAVIGATION_WAIT_MS)
        title = await page.title()
        body_text = await page.locator("body").inner_text()
        page_error = _classify_youtube_page_error(title, body_text, target_url)
        if page_error is not None:
            raise RuntimeError(page_error)
        html = await page.content()
        return html, navigation_timeout_error


def _build_section_url(entry_url: str, section: str) -> str:
    parsed = urlsplit(entry_url)
    path = parsed.path.rstrip("/")
    if not path.endswith(f"/{section}"):
        path = f"{path}/{section}" if path else f"/{section}"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def _classify_youtube_page_error(title: str, body_text: str, target_url: str) -> str | None:
    combined = f"{title}\n{body_text}".lower()
    if "5xx server error" in combined:
        return f"youtube returned error page for {target_url}: {title}"
    if "404 not found" in combined or "this page isn't available" in combined:
        return f"来源 URL 无效: {target_url}（页面不存在或频道不存在）"
    return None


def _extract_youtube_items(html: str, section: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = [
        "ytd-rich-item-renderer",
        "ytd-grid-video-renderer",
        "ytd-video-renderer",
        "ytd-reel-item-renderer",
    ]
    items: list[dict[str, object]] = []
    for node in soup.select(", ".join(selectors)):
        anchor = (
            node.select_one("a#video-title-link")
            or node.select_one("a#video-title")
            or node.select_one("a[href*='/watch']")
            or node.select_one("a[href*='/shorts']")
        )
        if anchor is None:
            continue

        href = (anchor.get("href") or "").strip()
        title = anchor.get("title") or anchor.get_text(strip=True)
        published_at = _extract_published_at_text(node)
        excerpt = node.get_text(" ", strip=True) or None
        items.append(
            {
                "title": title,
                "url": urljoin("https://www.youtube.com", href),
                "published_at": published_at,
                "excerpt": excerpt,
                "raw_payload": {
                    "section": section,
                    "title": title,
                    "url": href,
                    "published_at": published_at,
                },
            }
        )
    return items


def _extract_published_at_text(node) -> str | None:
    texts = _collect_metadata_texts(node)
    for text in texts:
        if _looks_like_published_at(text):
            return text
    return None


def _collect_metadata_texts(node) -> list[str]:
    selectors = ["#metadata-line span", "#metadata span", "span.inline-metadata-item"]
    texts: list[str] = []
    for selector in selectors:
        for candidate in node.select(selector):
            text = candidate.get_text(" ", strip=True)
            if text:
                texts.append(text)
    return texts


def _looks_like_published_at(text: str) -> bool:
    lowered = text.lower()
    if _VIEW_PATTERN.search(text):
        return False
    if _RELATIVE_PATTERN.search(lowered):
        return True
    if _TRADITIONAL_CHINESE_RELATIVE_PATTERN.search(text):
        return True
    if "today" in lowered or "yesterday" in lowered:
        return True
    if lowered.startswith("streamed ") and _RELATIVE_PATTERN.search(lowered):
        return True
    if _ENGLISH_DATE_PATTERN.search(text) or _ISO_DATE_PATTERN.search(text):
        return True
    return False


def _normalize_item(item: dict[str, object], section: str, published_on: date) -> dict[str, object] | None:
    title = str(item.get("title") or "").strip()
    url = str(item.get("url") or "").strip()
    if not title or not url:
        return None

    published_at = item.get("published_at")
    payload = dict(item.get("raw_payload") or item)
    payload.setdefault("section", section)
    normalized: dict[str, object] = {
        "title": title,
        "url": url,
        "published_at": published_at if published_at else published_on.isoformat(),
        "raw_payload": payload,
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


def _coerce_to_date(value, today: date) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    absolute_text = _extract_absolute_date_text(text)
    if absolute_text is not None:
        for pattern in _ABSOLUTE_PATTERNS:
            try:
                return datetime.strptime(absolute_text, pattern).date()
            except ValueError:
                pass

    iso_candidate = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_candidate).date()
    except ValueError:
        pass

    lowered = text.lower()
    if "yesterday" in lowered:
        return today - timedelta(days=1)
    if "today" in lowered:
        return today

    match = _RELATIVE_PATTERN.search(lowered)
    if match is not None:
        relative_value = int(match.group("value"))
        unit = match.group("unit").lower()
        days = {
            "minute": 0,
            "hour": 0,
            "day": relative_value,
            "week": relative_value * 7,
            "month": relative_value * 30,
            "year": relative_value * 365,
        }[unit]
        return today - timedelta(days=days)

    traditional_chinese_match = _TRADITIONAL_CHINESE_RELATIVE_PATTERN.search(text)
    if traditional_chinese_match is None:
        return None

    relative_value = int(traditional_chinese_match.group("value"))
    unit = traditional_chinese_match.group("unit")
    days = {
        "分鐘": 0,
        "小時": 0,
        "天": relative_value,
        "週": relative_value * 7,
        "周": relative_value * 7,
        "個月": relative_value * 30,
        "月": relative_value * 30,
        "年": relative_value * 365,
    }[unit]
    return today - timedelta(days=days)


def _extract_absolute_date_text(text: str) -> str | None:
    english_match = _ENGLISH_DATE_PATTERN.search(text)
    if english_match is not None:
        return english_match.group(0).replace("Sept", "Sep")

    iso_match = _ISO_DATE_PATTERN.search(text)
    if iso_match is not None:
        return iso_match.group(0)
    return None



