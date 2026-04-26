from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(slots=True)
class NormalizedContent:
    dedupe_key: str
    title: str
    canonical_url: str
    excerpt: str | None
    tags: list[str]
    raw_payload: dict[str, object]


class ContentNormalizerService:
    def normalize(self, *, source, raw_payload: dict[str, object]) -> NormalizedContent:
        title = str(raw_payload.get("title") or "").strip() or "未命名内容"
        canonical_url = str(raw_payload.get("url") or "").strip()
        excerpt = str(raw_payload.get("excerpt") or "").strip() or None
        tags = self._build_tags(source)
        dedupe_key = self._build_dedupe_key(title=title, canonical_url=canonical_url, raw_payload=raw_payload)
        return NormalizedContent(
            dedupe_key=dedupe_key,
            title=title,
            canonical_url=canonical_url,
            excerpt=excerpt,
            tags=tags,
            raw_payload=dict(raw_payload),
        )

    def _build_tags(self, source) -> list[str]:
        source_name = str(getattr(source, "name", "") or "").strip()
        return [source_name] if source_name else []

    def _build_dedupe_key(self, *, title: str, canonical_url: str, raw_payload: dict[str, object]) -> str:
        if canonical_url:
            raw_value = canonical_url
        else:
            published_at = str(raw_payload.get("published_at") or "").strip()
            raw_value = f"{title}|{published_at}"
        return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()
