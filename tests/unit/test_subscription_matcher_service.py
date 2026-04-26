from __future__ import annotations

from pathlib import Path

from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.models.content_item import ContentItem
from app.models.subscription import Subscription
from app.services.subscription_matcher_service import SubscriptionMatcherService


def setup_database(tmp_path: Path, name: str):
    import os

    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / name).as_posix()}"
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory()


def test_matcher_selects_subscription_by_business_line_and_keyword(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "subscription-matcher.db")

    with session_factory() as session:
        session.add(
            Subscription(
                code="hr-daily",
                channel="dingtalk",
                business_lines=["hr"],
                keywords=["校招"],
            )
        )
        session.add(
            ContentItem(
                dedupe_key="content-1",
                title="校招信息汇总",
                canonical_url="https://example.com/content-1",
                tags=["hr"],
                raw_payload={},
            )
        )
        session.commit()
        content_item = session.query(ContentItem).filter_by(dedupe_key="content-1").one()

        matched = SubscriptionMatcherService(session).match(content_item)

        assert [item.code for item in matched] == ["hr-daily"]
