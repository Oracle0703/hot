from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content_item import ContentItem
from app.models.raw_item import RawItem
from app.models.source import Source
from app.services.content_normalizer_service import ContentNormalizerService


@dataclass(slots=True)
class ContentPipelineResult:
    raw_count: int = 0
    content_count: int = 0
    content_items: list[ContentItem] = field(default_factory=list)


class ContentPipelineService:
    def __init__(self, session: Session, normalizer: ContentNormalizerService | None = None) -> None:
        self.session = session
        self.normalizer = normalizer or ContentNormalizerService()

    def ingest_run(self, job_id, source_runs: list[dict[str, object]]) -> ContentPipelineResult:
        result = ContentPipelineResult()
        seen_dedupe_keys: set[str] = set()
        staged_content_items: dict[str, ContentItem] = {}

        for run in source_runs:
            source_id = run.get("source_id")
            if source_id is None:
                continue
            source = self.session.get(Source, self._to_uuid(source_id))
            if source is None:
                continue
            for item in run.get("items", []) or []:
                payload = dict(item or {})
                self.session.add(
                    RawItem(
                        source_id=source.id,
                        job_id=job_id,
                        payload=payload,
                    )
                )
                result.raw_count += 1

                normalized = self.normalizer.normalize(source=source, raw_payload=payload)
                content_item = staged_content_items.get(normalized.dedupe_key)
                if content_item is None:
                    content_item = self.session.scalar(
                        select(ContentItem).where(ContentItem.dedupe_key == normalized.dedupe_key)
                    )
                if content_item is None:
                    content_item = ContentItem(
                        dedupe_key=normalized.dedupe_key,
                        title=normalized.title,
                        canonical_url=normalized.canonical_url,
                        excerpt=normalized.excerpt,
                        tags=normalized.tags,
                        raw_payload=normalized.raw_payload,
                    )
                    self.session.add(content_item)
                    staged_content_items[normalized.dedupe_key] = content_item
                    result.content_count += 1
                else:
                    content_item.title = normalized.title
                    content_item.canonical_url = normalized.canonical_url
                    content_item.excerpt = normalized.excerpt
                    content_item.tags = normalized.tags
                    content_item.raw_payload = normalized.raw_payload
                    staged_content_items[normalized.dedupe_key] = content_item

                if normalized.dedupe_key not in seen_dedupe_keys:
                    result.content_items.append(content_item)
                    seen_dedupe_keys.add(normalized.dedupe_key)

        self.session.flush()
        return result

    def _to_uuid(self, value) -> UUID:
        return value if isinstance(value, UUID) else UUID(str(value))
