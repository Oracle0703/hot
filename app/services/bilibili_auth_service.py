from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from pathlib import Path

from app.runtime_paths import get_runtime_paths
from app.services.app_env_service import AppEnvService, BilibiliEnvSettings
from app.services.network_access_policy import build_playwright_launch_kwargs

_PREFERRED_COOKIE_NAMES = (
    "SESSDATA",
    "bili_jct",
    "DedeUserID",
    "DedeUserID__ckMd5",
    "sid",
    "buvid3",
    "buvid4",
)


@dataclass(slots=True)
class BilibiliBrowserAuthResult:
    cookie: str
    storage_state_file: Path
    user_data_dir: Path
    settings: BilibiliEnvSettings


class BilibiliBrowserAuthService:
    def __init__(
        self,
        *,
        app_env_service: AppEnvService | None = None,
        start_url: str = "https://www.bilibili.com/",
        login_timeout_ms: int = 180000,
        poll_interval_ms: int = 1000,
        navigation_timeout_ms: int = 45000,
    ) -> None:
        self.app_env_service = app_env_service or AppEnvService()
        self.start_url = start_url
        self.login_timeout_ms = login_timeout_ms
        self.poll_interval_ms = poll_interval_ms
        self.navigation_timeout_ms = navigation_timeout_ms

    def login_and_sync(self) -> BilibiliBrowserAuthResult:
        return _run_awaitable_sync(self._login_and_sync())

    async def _login_and_sync(self) -> BilibiliBrowserAuthResult:
        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("playwright is not installed") from exc

        runtime_paths = get_runtime_paths()
        runtime_paths.ensure_directories()
        launch_kwargs = build_playwright_launch_kwargs(self.start_url, headless=False)

        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                str(runtime_paths.bilibili_user_data_dir),
                **launch_kwargs,
            )
            page = context.pages[0] if getattr(context, "pages", None) else await context.new_page()
            try:
                await page.goto(self.start_url, wait_until="domcontentloaded", timeout=self.navigation_timeout_ms)
                cookie_value = await self._wait_for_cookie(context)
                await context.storage_state(path=str(runtime_paths.bilibili_storage_state_file))
            finally:
                await context.close()

        settings = self.app_env_service.update_bilibili_settings(cookie=cookie_value)
        return BilibiliBrowserAuthResult(
            cookie=settings.cookie,
            storage_state_file=runtime_paths.bilibili_storage_state_file,
            user_data_dir=runtime_paths.bilibili_user_data_dir,
            settings=settings,
        )

    async def _wait_for_cookie(self, context) -> str:
        deadline = asyncio.get_running_loop().time() + max(self.login_timeout_ms, 1) / 1000
        while True:
            cookie_value = _build_cookie_string(await context.cookies())
            if "SESSDATA=" in cookie_value:
                return cookie_value
            if asyncio.get_running_loop().time() >= deadline:
                break
            await asyncio.sleep(max(self.poll_interval_ms, 1) / 1000)
        raise RuntimeError("B站浏览器登录超时，未检测到 SESSDATA")


def get_bilibili_storage_state_path() -> Path:
    return get_runtime_paths().bilibili_storage_state_file


def _build_cookie_string(cookies: list[dict[str, object]]) -> str:
    values_by_name: dict[str, str] = {}
    ordered_names: list[str] = []
    for cookie in cookies:
        name = str(cookie.get("name") or "").strip()
        value = str(cookie.get("value") or "").strip()
        domain = str(cookie.get("domain") or "").strip().lower()
        if not name or not value:
            continue
        if domain and "bilibili.com" not in domain:
            continue
        if name not in values_by_name:
            ordered_names.append(name)
        values_by_name[name] = value

    if not values_by_name:
        return ""

    names: list[str] = []
    for name in _PREFERRED_COOKIE_NAMES:
        if name in values_by_name:
            names.append(name)
    for name in ordered_names:
        if name not in names:
            names.append(name)
    return "; ".join(f"{name}={values_by_name[name]}" for name in names)


def _run_awaitable_sync(awaitable):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    result: dict[str, object] = {}
    error: dict[str, BaseException] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(awaitable)
        except BaseException as exc:  # pragma: no cover
            error["error"] = exc

    worker = threading.Thread(target=runner, daemon=True)
    worker.start()
    worker.join()

    if "error" in error:
        raise error["error"]
    return result["value"]
