from __future__ import annotations

from tests.conftest import create_test_client, make_sqlite_url


def test_create_site_account_returns_201_and_payload(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "site-accounts-api.db"))

    response = client.post(
        "/api/site-accounts",
        json={
            "platform": "bilibili",
            "account_key": "Creator A",
            "display_name": "账号A",
            "enabled": True,
            "is_default": False,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["platform"] == "bilibili"
    assert data["account_key"] == "creator-a"
    assert data["display_name"] == "账号A"
    assert data["enabled"] is True
    assert data["is_default"] is False
