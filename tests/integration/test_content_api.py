from __future__ import annotations

from app.api.routes_sources import SessionFactoryHolder
from app.models.content_item import ContentItem
from tests.conftest import create_test_client, make_sqlite_url


def test_content_api_lists_content_items(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "content-api-list.db"))

    response = client.get("/api/content")

    assert response.status_code == 200
    assert response.json() == []


def test_content_api_filters_by_title_and_tag(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "content-api-filter.db"))

    with SessionFactoryHolder.factory() as session:
        session.add_all(
            [
                ContentItem(
                    dedupe_key="content-api-filter-1",
                    title="校招信息汇总",
                    canonical_url="https://example.com/content-api-filter-1",
                    tags=["HR情报源", "校招"],
                    raw_payload={},
                ),
                ContentItem(
                    dedupe_key="content-api-filter-2",
                    title="版号情报汇总",
                    canonical_url="https://example.com/content-api-filter-2",
                    tags=["市场情报源"],
                    raw_payload={},
                ),
            ]
        )
        session.commit()

    response = client.get("/api/content?title=校招&tag=HR情报源")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "校招信息汇总"
