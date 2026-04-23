from __future__ import annotations

from urllib.parse import urlsplit

from app.config import Settings, get_settings


_LOCAL_BYPASS_HOSTS = ('localhost', '::1')


def _normalize_bypass_domains(raw_value: str) -> tuple[str, ...]:
    domains: list[str] = []
    for part in str(raw_value or '').split(','):
        normalized = part.strip().lower().lstrip('.')
        if normalized and normalized not in domains:
            domains.append(normalized)
    return tuple(domains)


def should_bypass_proxy(target_url: str, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    host = urlsplit(str(target_url or '')).hostname or ''
    normalized_host = host.strip().lower().rstrip('.')
    if not normalized_host:
        return False
    if normalized_host in _LOCAL_BYPASS_HOSTS or normalized_host.startswith('127.'):
        return True

    for domain in _normalize_bypass_domains(settings.outbound_proxy_bypass_domains):
        if normalized_host == domain or normalized_host.endswith(f'.{domain}'):
            return True
    return False


def build_playwright_launch_kwargs(target_url: str, settings: Settings | None = None, *, headless: bool = True) -> dict[str, object]:
    settings = settings or get_settings()
    launch_kwargs: dict[str, object] = {'headless': headless}

    proxy_url = settings.outbound_proxy_url.strip()
    if settings.enable_site_proxy_rules and proxy_url and not should_bypass_proxy(target_url, settings):
        launch_kwargs['proxy'] = {'server': proxy_url}
        return launch_kwargs

    launch_kwargs['args'] = ['--no-proxy-server']
    return launch_kwargs


async def launch_configured_chromium(chromium, target_url: str, settings: Settings | None = None, *, headless: bool = True):
    launch_kwargs = build_playwright_launch_kwargs(target_url, settings, headless=headless)
    try:
        return await chromium.launch(**launch_kwargs)
    except TypeError as exc:
        if 'unexpected keyword argument' not in str(exc):
            raise
        return await chromium.launch(headless=headless)


def build_httpx_request_kwargs(target_url: str, settings: Settings | None = None) -> dict[str, object]:
    settings = settings or get_settings()
    request_kwargs: dict[str, object] = {'trust_env': False}

    proxy_url = settings.outbound_proxy_url.strip()
    if settings.enable_site_proxy_rules and proxy_url and not should_bypass_proxy(target_url, settings):
        request_kwargs['proxy'] = proxy_url
    return request_kwargs
