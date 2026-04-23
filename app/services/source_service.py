from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.item import CollectedItem
from app.models.job_log import JobLog
from app.models.source import Source
from app.schemas.source import SourceCreate, SourceUpdate


_LEGACY_EPICGAMES_URL = 'https://www.youtube.com/@EpicGames'
_DEFAULT_SOURCE_ROWS: tuple[dict[str, object], ...] = (
    {
        'name': 'YouTube-ElectronicArts',
        'site_name': 'YouTube',
        'entry_url': 'https://www.youtube.com/@ElectronicArts',
        'fetch_mode': 'playwright',
        'source_group': 'overseas',
        'collection_strategy': 'youtube_channel_recent',
    },
    {
        'name': 'YouTube-EpicGames',
        'site_name': 'YouTube',
        'entry_url': 'https://www.youtube.com/@EpicGamesStore',
        'fetch_mode': 'playwright',
        'source_group': 'overseas',
        'collection_strategy': 'youtube_channel_recent',
    },
    {
        'name': 'B站-游戏-今日搜索',
        'site_name': 'Bilibili',
        'entry_url': 'https://www.bilibili.com/',
        'fetch_mode': 'playwright',
        'source_group': 'domestic',
        'collection_strategy': 'bilibili_site_search',
        'search_keyword': '游戏',
    },
)


class SourceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_source(self, source_id: str) -> Source | None:
        return self.session.get(Source, UUID(source_id))

    def list_sources(self) -> list[Source]:
        return self.session.query(Source).order_by(Source.id.asc()).all()

    def list_sources_by_group(self, group: str | None) -> list[Source]:
        statement = select(Source)
        if group is None:
            statement = statement.where(Source.source_group.is_(None))
        else:
            statement = statement.where(Source.source_group == group)
        statement = statement.order_by(Source.id.asc())
        return list(self.session.scalars(statement).all())

    def count_enabled_sources(self, group: str | None = None) -> int:
        statement = select(Source.id).where(Source.enabled.is_(True))
        if group is None:
            statement = statement.where(Source.source_group.is_(None))
        else:
            statement = statement.where(Source.source_group == group)
        return len(list(self.session.scalars(statement).all()))

    def create_source(self, data: SourceCreate) -> Source:
        source = Source(**data.model_dump())
        self.session.add(source)
        self.session.commit()
        self.session.refresh(source)
        return source

    def update_source(self, source_id: str, data: SourceUpdate) -> Source | None:
        source = self.session.get(Source, UUID(source_id))
        if source is None:
            return None

        for field_name, value in data.model_dump(exclude_unset=True).items():
            setattr(source, field_name, value)

        self.session.commit()
        self.session.refresh(source)
        return source

    def delete_source(self, source_id: str) -> bool:
        source_uuid = UUID(source_id)
        source = self.session.get(Source, source_uuid)
        if source is None:
            return False

        self.session.execute(update(JobLog).where(JobLog.source_id == source_uuid).values(source_id=None))
        self.session.execute(delete(CollectedItem).where(CollectedItem.source_id == source_uuid))
        self.session.execute(delete(Source).where(Source.id == source_uuid))
        self.session.commit()
        return True

    def seed_default_sources(self) -> int:
        default_names = [str(item['name']) for item in _DEFAULT_SOURCE_ROWS]
        existing_names = set(
            self.session.scalars(select(Source.name).where(Source.name.in_(default_names))).all()
        )

        created_count = 0
        for payload in _DEFAULT_SOURCE_ROWS:
            name = str(payload['name'])
            if name in existing_names:
                self._upgrade_legacy_seeded_source(name, payload)
                continue

            self.session.add(Source(**payload))
            try:
                self.session.commit()
            except IntegrityError as exc:
                self.session.rollback()
                is_name_already_created = self.session.scalar(select(Source.id).where(Source.name == name)) is not None
                if is_name_already_created:
                    existing_names.add(name)
                    self._upgrade_legacy_seeded_source(name, payload)
                    continue
                raise exc

            existing_names.add(name)
            created_count += 1

        return created_count

    def _upgrade_legacy_seeded_source(self, name: str, payload: dict[str, object]) -> None:
        if name != 'YouTube-EpicGames':
            return

        source = self.session.scalar(select(Source).where(Source.name == name))
        if source is None:
            return
        if source.entry_url != _LEGACY_EPICGAMES_URL:
            return
        if getattr(source, 'collection_strategy', None) != payload.get('collection_strategy'):
            return

        source.entry_url = str(payload['entry_url'])
        self.session.commit()
        self.session.refresh(source)

