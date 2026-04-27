from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.config import get_settings
from app.services.auth_state_service import AuthStateService
from app.services.bilibili_video_detail_service import fetch_bilibili_video_detail_by_url
from app.services.network_access_policy import launch_configured_chromium
from app.services.strategies import run_awaitable_sync


logger = logging.getLogger(__name__)
_SPACE_PATH_RE = re.compile(r"^/(?P<mid>\d+)(?:/)?$")
_SUPPORTED_VIDEO_PATH_RE = re.compile(r"^/video/(?:BV[0-9A-Za-z]+|av\d+)(?:[/?#]|$)")
_SUPPORTED_VIDEO_HOSTS = {"www.bilibili.com", "m.bilibili.com"}
_LOGIN_REQUIRED_MARKERS = (
    "请先登录",
    "登录后查看更多投稿视频",
    "登录后查看更多",
    "扫码登录",
)
_RISK_CONTROL_MARKERS = (
    "访问频繁",
    "访问存在风险",
    "当前访问存在风险",
    "请稍后再试",
    "安全验证",
    "账号异常",
    "风控",
)
_RETRYABLE_FAILURE_MARKERS = (
    "风控",
    "risk control",
    "redirected to unexpected url",
    "请稍后再试",
    "访问频繁",
    "访问存在风险",
    "当前访问存在风险",
)
_DEFAULT_RETRY_DELAY_SECONDS = 5.0


class BilibiliProfileVideosRecentStrategy:
    def __init__(self, runner=None, sleeper=None, detail_fetcher=None, auth_state_service: AuthStateService | None = None) -> None:
        self.auth_state_service = auth_state_service or AuthStateService()
        self.runner = runner or _PlaywrightBilibiliProfileRunner(auth_state_service=self.auth_state_service)
        self.sleeper = sleeper or time.sleep
        self.detail_fetcher = detail_fetcher or fetch_bilibili_video_detail_by_url

    def execute(self, source) -> list[dict[str, object]]:
        entry_url = str(getattr(source, "entry_url", "") or "").strip()
        if not _is_supported_entry_url(entry_url):
            raise ValueError("bilibili profile videos currently only supports https://space.bilibili.com/<mid>")

        raw_limit = getattr(source, "max_items", 30)
        max_items = 30 if raw_limit is None else int(raw_limit)
        if max_items <= 0:
            return []

        items: list[dict[str, object]] = []
        seen_urls: set[str] = set()
        raw_items = self._fetch_items_with_retry(source)
        for raw_item in raw_items:
            normalized = _normalize_item(raw_item)
            if normalized is None:
                continue
            normalized = self._enrich_item_with_detail(normalized)
            url = normalized["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            items.append(normalized)
            if len(items) >= max_items:
                break
        return items

    def _fetch_items_with_retry(self, source) -> list[dict[str, object]]:
        try:
            return self.runner.fetch_items(source)
        except RuntimeError as exc:
            if not _is_retryable_profile_fetch_error(exc):
                raise
            logger.warning("bilibili profile fetch retry once after retryable error: %s", exc)
            self.sleeper(_get_bilibili_retry_delay_seconds())
            return self.runner.fetch_items(source)

    def _enrich_item_with_detail(self, item: dict[str, object]) -> dict[str, object]:
        detail = self.detail_fetcher(str(item.get("url") or "").strip())
        if not detail:
            return item
        enriched = dict(item)
        for key in ("author", "published_at_text", "cover_image_url", "like_count", "reply_count", "view_count"):
            value = detail.get(key)
            if value is not None:
                enriched[key] = value
        return enriched


class _PlaywrightBilibiliProfileRunner:
    def __init__(self, auth_state_service: AuthStateService | None = None) -> None:
        self.auth_state_service = auth_state_service or AuthStateService()

    def fetch_items(self, source) -> list[dict[str, object]]:
        return run_awaitable_sync(self._fetch_items(source))

    async def _fetch_items(self, source) -> list[dict[str, object]]:
        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("playwright is not installed") from exc

        target_url = _build_video_page_url(str(getattr(source, "entry_url", "") or ""))
        cookie_value = _get_required_bilibili_cookie(source)
        parsed_cookies = _parse_bilibili_cookie_string(cookie_value)
        cookie_names = [cookie["name"] for cookie in parsed_cookies]
        api_payload: dict[str, object] | None = None
        logger.info(
            "bilibili profile fetch start: target_url=%s cookie_names=%s",
            target_url,
            cookie_names,
        )
        async with async_playwright() as playwright:
            browser = await launch_configured_chromium(playwright.chromium, target_url)
            context = await browser.new_context(**_build_context_kwargs(source, auth_state_service=self.auth_state_service))
            await context.add_cookies(parsed_cookies)
            logger.info(
                "bilibili profile cookies loaded: target_url=%s cookie_names=%s",
                target_url,
                cookie_names,
            )
            page = await context.new_page()

            async def on_response(resp) -> None:
                nonlocal api_payload
                if api_payload is not None:
                    return
                if not resp.url.startswith("https://api.bilibili.com/x/space/wbi/arc/search"):
                    return
                try:
                    api_payload = await resp.json()
                except Exception:
                    try:
                        api_payload = json.loads(await resp.text())
                    except Exception:
                        api_payload = {"code": -1, "message": "bilibili profile api returned invalid payload"}
                logger.info(
                    "bilibili profile api response: target_url=%s api_code=%s",
                    target_url,
                    api_payload.get("code") if isinstance(api_payload, dict) else None,
                )

            page.on("response", on_response)
            try:
                await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(5000)
                _ensure_expected_profile_video_page_url(getattr(page, "url", target_url), target_url)
                if api_payload is not None:
                    api_items = _extract_items_from_api_payload_or_none(api_payload, target_url=target_url)
                    if api_items is not None:
                        return api_items
                html = await page.content()
            finally:
                await page.close()
                await context.close()
                await browser.close()

        _ensure_profile_page_accessible(html)
        items = _extract_bilibili_profile_video_items(html)
        logger.info(
            "bilibili profile html fallback parsed: target_url=%s item_count=%s cookie_names=%s",
            target_url,
            len(items),
            cookie_names,
        )
        return items


def _get_required_bilibili_cookie(source=None) -> str:
    value = str(getattr(source, "account_cookie", "") or "").strip()
    if not value:
        value = get_settings().bilibili_cookie.strip()
    if not value:
        raise RuntimeError("BILIBILI_COOKIE is required for bilibili_profile_videos_recent strategy")
    return value


def _parse_bilibili_cookie_string(cookie_value: str) -> list[dict[str, object]]:
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
    if not cookies:
        raise RuntimeError("BILIBILI_COOKIE is invalid for bilibili_profile_videos_recent strategy")
    return cookies


def _is_supported_entry_url(entry_url: str) -> bool:
    parsed = urlsplit(entry_url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "space.bilibili.com":
        return False
    return _SPACE_PATH_RE.match(parsed.path.rstrip("/") or parsed.path) is not None


def _extract_mid(entry_url: str) -> str:
    parsed = urlsplit(entry_url)
    match = _SPACE_PATH_RE.match(parsed.path.rstrip("/") or parsed.path)
    if match is None:
        raise ValueError("bilibili profile videos currently only supports https://space.bilibili.com/<mid>")
    return match.group("mid")


def _build_video_page_url(entry_url: str) -> str:
    mid = _extract_mid(entry_url)
    return urlunsplit(("https", "space.bilibili.com", f"/{mid}/video", "", ""))


def _extract_items_from_api_payload(payload: dict[str, object]) -> list[dict[str, object]]:
    code = int(payload.get("code", -1) or 0)
    if code != 0:
        message = str(payload.get("message") or "unknown error").strip()
        if code in {-352, -412} or any(marker in message for marker in _RISK_CONTROL_MARKERS):
            raise RuntimeError(f"bilibili profile api hit risk control (风控): code={code}, message={message}")
        raise RuntimeError(f"bilibili profile api returned error: code={code}, message={message}")

    data = payload.get("data") or {}
    listing = data.get("list") or {}
    vlist = listing.get("vlist") or []
    items: list[dict[str, object]] = []
    for raw in vlist:
        title = str(raw.get("title") or "").strip()
        bvid = str(raw.get("bvid") or "").strip()
        if not title or not bvid:
            continue
        created = raw.get("created")
        published_at = None
        if created:
            try:
                published_at = datetime.fromtimestamp(int(created)).strftime("%Y-%m-%d")
            except (TypeError, ValueError, OSError):
                published_at = None
        description = str(raw.get("description") or "").strip() or None
        author = str(raw.get("author") or "").strip() or None
        item: dict[str, object] = {
            "title": title,
            "url": f"https://www.bilibili.com/video/{bvid}",
            "published_at": published_at,
            "raw_payload": dict(raw),
        }
        if description:
            item["excerpt"] = description
        if author:
            item["author"] = author
        items.append(item)
    return items


def _extract_items_from_api_payload_or_none(
    payload: dict[str, object],
    *,
    target_url: str,
) -> list[dict[str, object]] | None:
    try:
        return _extract_items_from_api_payload(payload)
    except RuntimeError as exc:
        logger.warning(
            "bilibili profile api fallback to html: target_url=%s error=%s",
            target_url,
            exc,
        )
        return None


def _build_context_kwargs(source=None, auth_state_service: AuthStateService | None = None) -> dict[str, object]:
    kwargs: dict[str, object] = {"ignore_https_errors": True}
    account_key = str(getattr(source, "account_key", "") or "default").strip() or "default"
    storage_state_file = (auth_state_service or AuthStateService()).build_paths("bilibili", account_key).storage_state_file
    if storage_state_file.exists():
        kwargs["storage_state"] = str(storage_state_file)
    return kwargs


def _ensure_profile_page_accessible(html: str) -> None:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    if any(marker in text for marker in _LOGIN_REQUIRED_MARKERS):
        raise RuntimeError("bilibili profile page requires login (登录失效); 请刷新 BILIBILI_COOKIE")
    if any(marker in text for marker in _RISK_CONTROL_MARKERS):
        raise RuntimeError("bilibili profile page hit risk control (风控); 请稍后重试或刷新 BILIBILI_COOKIE")


def _ensure_expected_profile_video_page_url(current_url: str, target_url: str) -> None:
    current = urlsplit(str(current_url or "").strip())
    target = urlsplit(target_url)
    target_mid = target.path.strip("/").split("/", 1)[0]
    current_path_parts = current.path.strip("/").split("/", 1)
    current_mid = current_path_parts[0] if current_path_parts else ""
    if current.scheme == target.scheme and current.netloc.lower() == target.netloc.lower() and current_mid == target_mid:
        return
    raise RuntimeError(
        f"bilibili profile page redirected to unexpected url (可能触发风控或登录失效): {urlunsplit(current)}"
    )


def _extract_bilibili_profile_video_items(html: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = [
        "div.list-item",
        "div.small-item",
        "li.small-item",
        "div.bili-video-card",
        "div[data-type='video']",
    ]
    nodes = []
    for selector in selectors:
        nodes.extend(soup.select(selector))

    if not nodes:
        nodes = list(soup.select("a[href*='/video/']"))

    items: list[dict[str, object]] = []
    for node in nodes:
        anchor = _select_video_anchor(node)
        if anchor is None:
            continue
        href = str(anchor.get("href") or "").strip()
        title = _extract_title(node, anchor)
        if not href or not title:
            continue
        published_at = _extract_published_at(node)
        url = _normalize_video_url(href)
        if url is None:
            continue
        excerpt = node.get_text(" ", strip=True) or None
        items.append(
            {
                "title": title,
                "url": url,
                "published_at": published_at,
                "excerpt": excerpt,
                "raw_payload": {
                    "url": href,
                    "published_at": published_at,
                },
            }
        )
    return items


def _select_video_anchor(node):
    if getattr(node, "name", None) == "a":
        return node if _normalize_video_url(node.get("href")) else None

    selectors = [
        ".bili-video-card__details .bili-video-card__title a[href]",
        ".bili-video-card__details a[href]",
        "a.title[href]",
        "a[href*='/video/'][title]",
        "a[href*='/video/']",
    ]
    for selector in selectors:
        for anchor in node.select(selector):
            if _normalize_video_url(anchor.get("href")):
                return anchor
    return None


def _normalize_video_url(href: str | None) -> str | None:
    value = str(href or "").strip()
    if not value:
        return None
    if value.startswith("//"):
        value = f"https:{value}"
    normalized = urljoin("https://www.bilibili.com", value)
    parsed = urlsplit(normalized)
    if parsed.scheme != "https":
        return None
    if parsed.netloc.lower() not in _SUPPORTED_VIDEO_HOSTS:
        return None
    if _SUPPORTED_VIDEO_PATH_RE.match(parsed.path) is None:
        return None
    return normalized


def _extract_title(node, anchor) -> str:
    detail_selectors = [
        ".bili-video-card__details .bili-video-card__title[title]",
        ".bili-video-card__details .bili-video-card__title a[title]",
        ".bili-video-card__details .bili-video-card__title a[href]",
    ]
    if hasattr(node, "select_one"):
        for selector in detail_selectors:
            candidate = node.select_one(selector)
            if candidate is None:
                continue
            title = str(candidate.get("title") or candidate.get_text(" ", strip=True) or "").strip()
            if title:
                return title

    return str(anchor.get("title") or anchor.get_text(" ", strip=True) or "").strip()


def _extract_published_at(node) -> str | None:
    selectors = [".bili-video-card__subtitle span", ".bili-video-card__subtitle", ".time", ".meta .time", ".bili-video-card__info--date", ".pubdate"]
    for selector in selectors:
        candidate = node.select_one(selector) if hasattr(node, "select_one") else None
        if candidate is None:
            continue
        text = candidate.get_text(" ", strip=True)
        if text:
            return text
    return None


def _is_retryable_profile_fetch_error(exc: RuntimeError) -> bool:
    message = str(exc).strip().lower()
    return any(marker.lower() in message for marker in _RETRYABLE_FAILURE_MARKERS)


def _get_bilibili_retry_delay_seconds() -> float:
    value = getattr(get_settings(), "bilibili_retry_delay_seconds", _DEFAULT_RETRY_DELAY_SECONDS)
    try:
        return float(max(int(value), 0))
    except (TypeError, ValueError):
        return _DEFAULT_RETRY_DELAY_SECONDS


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
    author = str(item.get("author") or "").strip()
    if author:
        normalized["author"] = author
    for key in ("published_at_text", "cover_image_url", "like_count", "reply_count", "view_count"):
        value = item.get(key)
        if value is not None:
            normalized[key] = value
    return normalized




