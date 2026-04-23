from __future__ import annotations

from app.config import Settings
from app.services.network_access_policy import (
    build_httpx_request_kwargs,
    build_playwright_launch_kwargs,
    should_bypass_proxy,
)


def test_should_bypass_proxy_for_bilibili_host_suffix() -> None:
    settings = Settings(
        enable_site_proxy_rules=True,
        outbound_proxy_url='http://127.0.0.1:7890',
        outbound_proxy_bypass_domains='bilibili.com,hdslb.com,bilivideo.com',
    )

    assert should_bypass_proxy('https://space.bilibili.com/20411266', settings) is True
    assert should_bypass_proxy('https://api.bilibili.com/x/web-interface/nav', settings) is True
    assert should_bypass_proxy('https://www.youtube.com/@ElectronicArts', settings) is False


def test_build_playwright_launch_kwargs_uses_direct_for_bilibili() -> None:
    settings = Settings(
        enable_site_proxy_rules=True,
        outbound_proxy_url='http://127.0.0.1:7890',
        outbound_proxy_bypass_domains='bilibili.com,hdslb.com,bilivideo.com',
    )

    kwargs = build_playwright_launch_kwargs('https://space.bilibili.com/20411266', settings)

    assert kwargs['headless'] is True
    assert kwargs['args'] == ['--no-proxy-server']
    assert 'proxy' not in kwargs


def test_build_playwright_launch_kwargs_uses_proxy_for_x() -> None:
    settings = Settings(
        enable_site_proxy_rules=True,
        outbound_proxy_url='http://127.0.0.1:7890',
        outbound_proxy_bypass_domains='bilibili.com,hdslb.com,bilivideo.com',
    )

    kwargs = build_playwright_launch_kwargs('https://x.com/PUBG', settings)

    assert kwargs['proxy'] == {'server': 'http://127.0.0.1:7890'}
    assert 'args' not in kwargs


def test_build_httpx_request_kwargs_disables_env_proxy_for_direct_bilibili() -> None:
    settings = Settings(
        enable_site_proxy_rules=True,
        outbound_proxy_url='http://127.0.0.1:7890',
        outbound_proxy_bypass_domains='bilibili.com,hdslb.com,bilivideo.com',
    )

    kwargs = build_httpx_request_kwargs('https://search.bilibili.com/all?keyword=test', settings)

    assert kwargs['trust_env'] is False
    assert 'proxy' not in kwargs


def test_build_httpx_request_kwargs_uses_proxy_for_youtube() -> None:
    settings = Settings(
        enable_site_proxy_rules=True,
        outbound_proxy_url='http://127.0.0.1:7890',
        outbound_proxy_bypass_domains='bilibili.com,hdslb.com,bilivideo.com',
    )

    kwargs = build_httpx_request_kwargs('https://www.youtube.com/@ElectronicArts', settings)

    assert kwargs['trust_env'] is False
    assert kwargs['proxy'] == 'http://127.0.0.1:7890'


def test_build_playwright_launch_kwargs_defaults_to_direct_without_proxy_url() -> None:
    kwargs = build_playwright_launch_kwargs('https://www.youtube.com/@ElectronicArts', Settings())

    assert kwargs['headless'] is True
    assert kwargs['args'] == ['--no-proxy-server']
    assert 'proxy' not in kwargs


def test_build_httpx_request_kwargs_defaults_to_direct_without_proxy_url() -> None:
    kwargs = build_httpx_request_kwargs('https://www.youtube.com/@ElectronicArts', Settings())

    assert kwargs == {'trust_env': False}
