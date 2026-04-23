from tests.conftest import create_test_client, make_sqlite_url


def test_create_manual_job_counts_enabled_sources(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "jobs-create.db"))
    client.post(
        "/api/sources",
        json={
            "name": "NGA 热点帖",
            "site_name": "NGA",
            "entry_url": "https://example.com/nga",
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "max_items": 30,
            "enabled": True,
        },
    )
    client.post(
        "/api/sources",
        json={
            "name": "TapTap 动态",
            "site_name": "TapTap",
            "entry_url": "https://example.com/taptap",
            "fetch_mode": "playwright",
            "parser_type": "generic_css",
            "max_items": 20,
            "enabled": False,
        },
    )

    response = client.post("/api/jobs")

    assert response.status_code == 201
    data = response.json()
    assert data["trigger_type"] == "manual"
    assert data["status"] == "pending"
    assert data["total_sources"] == 1
    assert data["completed_sources"] == 0
    assert data["success_sources"] == 0
    assert data["failed_sources"] == 0
    assert data["current_source"] is None
    assert data["report_id"] is None


def test_get_job_returns_created_job(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "jobs-detail.db"))
    created = client.post("/api/jobs").json()

    response = client.get(f"/api/jobs/{created['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created["id"]
    assert data["status"] == "pending"


def test_get_job_logs_returns_empty_list_for_new_job(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "jobs-logs.db"))
    created = client.post("/api/jobs").json()

    response = client.get(f"/api/jobs/{created['id']}/logs")

    assert response.status_code == 200
    assert response.json() == []
