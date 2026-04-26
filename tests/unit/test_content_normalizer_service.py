from __future__ import annotations

from types import SimpleNamespace

from app.services.content_normalizer_service import ContentNormalizerService


def test_content_normalizer_prefers_url_as_dedupe_key() -> None:
    normalizer = ContentNormalizerService()

    normalized = normalizer.normalize(
        source=SimpleNamespace(name="来源A"),
        raw_payload={
            "title": "校招信息",
            "url": "https://example.com/jobs/1",
            "excerpt": "岗位详情",
        },
    )

    assert normalized.title == "校招信息"
    assert normalized.canonical_url == "https://example.com/jobs/1"
    assert normalized.tags == ["来源A"]
    assert normalized.dedupe_key


def test_content_normalizer_falls_back_to_title_and_published_at_without_url() -> None:
    normalizer = ContentNormalizerService()

    normalized = normalizer.normalize(
        source=SimpleNamespace(name="来源B"),
        raw_payload={
            "title": "无链接帖子",
            "published_at": "2026-04-24 09:00",
        },
    )

    assert normalized.title == "无链接帖子"
    assert normalized.canonical_url == ""
    assert normalized.dedupe_key
