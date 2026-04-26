from __future__ import annotations

from app.api.routes_sources import SessionFactoryHolder
from app.models.subscription import Subscription
from tests.conftest import create_test_client, make_sqlite_url


def test_subscription_api_creates_rule(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "subscription-api-create.db"))

    response = client.post(
        "/api/subscriptions",
        json={
            "code": "hr-daily",
            "channel": "dingtalk",
            "business_lines": ["hr"],
            "keywords": ["校招"],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["code"] == "hr-daily"
    assert data["channel"] == "dingtalk"
    assert data["business_lines"] == ["hr"]
    assert data["keywords"] == ["校招"]


def test_subscription_api_filters_by_code_and_channel(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "subscription-api-filter.db"))

    with SessionFactoryHolder.factory() as session:
        session.add_all(
            [
                Subscription(
                    code="hr-daily",
                    channel="dingtalk",
                    business_lines=["hr"],
                    keywords=["校招"],
                ),
                Subscription(
                    code="market-daily",
                    channel="email",
                    business_lines=["market"],
                    keywords=["版号"],
                ),
            ]
        )
        session.commit()

    response = client.get("/api/subscriptions?code=hr&channel=dingtalk")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["code"] == "hr-daily"
