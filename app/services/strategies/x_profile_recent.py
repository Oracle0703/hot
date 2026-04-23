from __future__ import annotations

import os
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.config import get_settings
from app.services.network_access_policy import launch_configured_chromium
from app.services.strategies import run_awaitable_sync

_DEFAULT_WAIT_MS = 6000
_LOGIN_WALL_KEYWORDS = (
    "Log in",
    "Sign up",
    "See new posts",
)


class XProfileRecentStrategy:
    def __init__(self, runner=None) -> None:
        self.runner = runner or _PlaywrightXRunner()

    def execute(self, source) -> list[dict[str, object]]:
        raw_limit = getattr(source, "max_items", 30)
        max_items = 30 if raw_limit is None else int(raw_limit)
        if max_items <= 0:
            return []

        items = self.runner.fetch_items(source)
        return list(items[:max_items])


class _PlaywrightXRunner:
    def fetch_items(self, source) -> list[dict[str, object]]:
        return run_awaitable_sync(self._fetch_items(source))

    async def _fetch_items(self, source) -> list[dict[str, object]]:
        auth_token = _get_required_cookie("X_AUTH_TOKEN")
        ct0 = _get_required_cookie("X_CT0")

        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("playwright is not installed") from exc

        target_url = _normalize_x_entry_url(str(getattr(source, "entry_url", "") or ""))
        async with async_playwright() as playwright:
            browser = await launch_configured_chromium(playwright.chromium, target_url)
            context = await browser.new_context(ignore_https_errors=True)
            await context.add_cookies(
                [
                    {
                        "name": "auth_token",
                        "value": auth_token,
                        "domain": ".x.com",
                        "path": "/",
                        "httpOnly": True,
                        "secure": True,
                        "sameSite": "None",
                    },
                    {
                        "name": "ct0",
                        "value": ct0,
                        "domain": ".x.com",
                        "path": "/",
                        "httpOnly": False,
                        "secure": True,
                        "sameSite": "Lax",
                    },
                ]
            )
            page = await context.new_page()
            try:
                await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(_DEFAULT_WAIT_MS)
                title = await page.title()
                body_text = await page.locator("body").inner_text()
                page_error = _classify_x_page_error(title, body_text, target_url)
                if page_error is not None:
                    raise RuntimeError(page_error)
                html = await page.content()
            finally:
                await page.close()
                await browser.close()
        return _extract_x_items(html, target_url)



def _normalize_x_entry_url(entry_url: str) -> str:
    value = str(entry_url or '').strip()
    lowered = value.lower()
    if lowered.startswith('htps://'):
        value = 'https://' + value[8:]
    elif lowered.startswith('htps:/'):
        value = 'https://' + value[6:]
    elif lowered.startswith('https:/') and not lowered.startswith('https://'):
        value = 'https://' + value[7:]
    elif lowered.startswith('http:/') and not lowered.startswith('http://'):
        value = 'http://' + value[6:]

    reparsed = urlsplit(value)
    if not reparsed.netloc:
        for host in ('x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'):
            if value.lower() == host or value.lower().startswith(host + '/'):
                value = 'https://' + value.lstrip('/')
                reparsed = urlsplit(value)
                break

    allowed_hosts = {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'}
    if reparsed.scheme not in {'http', 'https'} or reparsed.netloc.lower() not in allowed_hosts:
        raise ValueError('x_profile_recent currently only supports https://x.com/<profile> or https://twitter.com/<profile>')

    path_parts = [part for part in reparsed.path.split('/') if part]
    if not path_parts:
        raise ValueError('x_profile_recent currently only supports https://x.com/<profile> or https://twitter.com/<profile>')

    normalized_path = '/' + '/'.join(path_parts)
    return urlunsplit(('https', reparsed.netloc, normalized_path, reparsed.query, ''))
def _get_required_cookie(name: str) -> str:
    get_settings()
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for x_profile_recent strategy")
    return value


def _classify_x_page_error(title: str, body_text: str, target_url: str) -> str | None:
    combined = f"{title}\n{body_text}"
    if all(keyword in combined for keyword in _LOGIN_WALL_KEYWORDS):
        return f"X 页面仍然返回登录墙，请检查登录态是否有效: {target_url}"
    if "Something went wrong" in combined and "@PUBG" not in combined and "PUBG: BATTLEGROUNDS" not in combined:
        return f"X 页面加载失败: {target_url}"
    return None


def _extract_x_items(html: str, base_url: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, object]] = []
    seen_urls: set[str] = set()

    for article in soup.select('article[data-testid="tweet"]'):
        status_path = ""
        published_at = None
        time_node = article.select_one("time")
        if time_node is not None:
            published_at = (time_node.get("datetime") or "").strip() or None
            parent_link = time_node.find_parent("a")
            if parent_link is not None:
                status_path = (parent_link.get("href") or "").strip()

        if not status_path:
            for anchor in article.select("a[href]"):
                href = (anchor.get("href") or "").strip()
                if "/status/" in href:
                    status_path = href
                    break

        text_parts: list[str] = []
        for node in article.select('[data-testid="tweetText"]'):
            text = node.get_text(" ", strip=True)
            if text:
                text_parts.append(text)
        title = "\n".join(text_parts).strip()

        if not title or not status_path:
            continue

        url = urljoin(base_url, status_path)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        items.append(
            {
                "title": title,
                "url": url,
                "published_at": published_at,
                "excerpt": title,
                "image_urls": _extract_tweet_image_urls(article),
                "raw_payload": {
                    "status_path": status_path,
                },
            }
        )

    return items


def _extract_tweet_image_urls(article) -> list[str]:
    image_urls: list[str] = []
    for image in article.select("img[src]"):
        src = str(image.get("src") or "").strip()
        if not src.startswith("https://pbs.twimg.com/"):
            continue
        if "/profile_images/" in src:
            continue
        if "/emoji/" in src:
            continue
        if src not in image_urls:
            image_urls.append(src)
    return image_urls

