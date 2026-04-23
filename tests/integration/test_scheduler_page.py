from tests.conftest import create_test_client, make_sqlite_url


def test_scheduler_page_shows_current_settings(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "scheduler-page.db"))

    response = client.get("/scheduler")

    assert response.status_code == 200
    assert "定时调度" in response.text
    assert "name='daily_time'" in response.text
    assert "08:00" in response.text


def test_scheduler_page_can_save_settings(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "scheduler-save.db"))

    response = client.post(
        "/scheduler",
        data={
            "enabled": "true",
            "daily_time": "09:30",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "09:30" in response.text
    assert "已启用" in response.text
