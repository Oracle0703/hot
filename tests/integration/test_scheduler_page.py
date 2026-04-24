from app.api.routes_sources import SessionFactoryHolder
from app.models.schedule_plan import SchedulePlan
from tests.conftest import create_test_client, make_sqlite_url


def test_scheduler_page_shows_current_settings(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "scheduler-page.db"))

    response = client.get("/scheduler")

    assert response.status_code == 200
    assert "定时调度" in response.text
    assert "调度计划" in response.text
    assert "name='run_time'" in response.text
    assert "name='schedule_group'" in response.text
    assert "未分组来源不会参与任何定时任务" in response.text


def test_scheduler_page_can_create_schedule_plan(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "scheduler-save.db"))

    response = client.post(
        "/scheduler/plans",
        data={
            "enabled": "true",
            "run_time": "09:30",
            "schedule_group": "morning",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "09:30" in response.text
    assert "morning" in response.text

    with SessionFactoryHolder.factory() as session:
        plans = session.query(SchedulePlan).all()

    assert len(plans) == 1
    assert plans[0].run_time == "09:30"
    assert plans[0].schedule_group == "morning"
