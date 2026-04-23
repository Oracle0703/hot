from __future__ import annotations

from app.services.network_access_policy import launch_configured_chromium


class PlaywrightCollector:
    async def fetch(self, source) -> str:
        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("playwright is not installed") from exc

        async with async_playwright() as playwright:
            browser = await launch_configured_chromium(playwright.chromium, source.entry_url)
            page = await browser.new_page()
            await page.goto(source.entry_url, wait_until="networkidle", timeout=45000)
            content = await page.content()
            await browser.close()
            return content

