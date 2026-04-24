import time
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.api.routes_sources import SessionFactoryHolder
from app.runtime_paths import get_runtime_paths
from app.models.job import CollectionJob
from app.models.job_log import JobLog
from tests.conftest import create_test_client, make_sqlite_url


HTML_SOURCE = """
<html>
  <body>
    <ul class='topics'>
      <li class='topic'>
        <a class='topic-link' href='https://example.com/post-1'>重磅新游版号过审</a>
        <span class='topic-time'>2026-03-24 08:00</span>
      </li>
    </ul>
  </body>
</html>
""".strip()


BROKEN_HTML_SOURCE = "file:///not-found/missing.html"


def test_index_page_shows_dashboard_actions(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-index.db"))

    response = client.get("/")

    assert response.status_code == 200
    assert "热点信息采集系统" in response.text
    assert "app-shell" in response.text
    assert "page-hero" in response.text
    assert "dashboard-status-bar" in response.text
    assert "dashboard-main-grid" in response.text
    assert "compact-quick-links" in response.text
    assert "dashboard-primary-panel" in response.text
    assert "dashboard-secondary-panel" in response.text
    assert "dashboard-featured-card" in response.text
    assert "dashboard-primary-actions" in response.text
    assert "dashboard-secondary-actions" in response.text
    assert "dashboard-empty-schedule-hint" in response.text
    assert "stat-card" in response.text
    assert "热点信号总览" in response.text
    assert "最近任务结果" in response.text
    assert "featured-latest-job" in response.text
    assert "recent-jobs" in response.text
    assert "recent-jobs-timeline" in response.text
    assert "quick-actions" in response.text
    assert "system-status-panel" not in response.text
    assert "立即采集国内" in response.text
    assert "立即采集国外" in response.text
    assert "按调度分组运行" in response.text
    assert "/jobs/run/domestic" in response.text
    assert "/jobs/run/overseas" in response.text
    assert "/sources" in response.text
    assert "/reports" in response.text
    assert "/weekly" in response.text


def test_post_run_job_redirects_to_job_detail_page(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-run.db"))

    response = client.post("/jobs/run", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/jobs/")


def test_job_detail_page_shows_progress_and_log_sections(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-detail.db"))
    created = client.post("/api/jobs").json()

    response = client.get(f"/jobs/{created['id']}")

    assert response.status_code == 200
    assert "任务详情" in response.text
    assert "body class='app-shell theme-dark'" in response.text
    assert "page-header" in response.text
    assert "job-detail-layout" in response.text
    assert "progress-panel" in response.text
    assert "log-panel" in response.text
    assert "job-log-list" in response.text
    assert f"/jobs/{created['id']}/progress" in response.text
    assert f"/jobs/{created['id']}/logs/view" in response.text
    assert "setInterval" in response.text
    assert "执行范围：全部" in response.text


def test_job_detail_page_shows_domestic_scope_label(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-detail-domestic-scope.db"))
    client.post(
        "/api/sources",
        json={
            "name": "国内来源",
            "site_name": "NGA",
            "entry_url": "https://example.com/domestic",
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 30,
            "enabled": True,
            "source_group": "domestic",
        },
    )

    run_response = client.post("/jobs/run/domestic", follow_redirects=False)
    job_id = run_response.headers["location"].rsplit("/", 1)[-1]
    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    assert "执行范围：国内" in response.text


def test_index_page_shows_latest_job_summary(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-summary.db"))
    client.post("/api/jobs")

    response = client.get("/")

    assert response.status_code == 200
    assert "最近任务" in response.text
    assert "pending" in response.text


def test_index_page_shows_only_latest_three_jobs_in_desc_order_with_collection_time(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-summary-order.db"))

    created_ids: list[str] = []
    for _ in range(4):
        created = client.post("/api/jobs").json()
        created_ids.append(created["id"])

    with SessionFactoryHolder.factory() as session:
        timestamps = [
            datetime(2026, 4, 8, 9, 0),
            datetime(2026, 4, 8, 9, 10),
            datetime(2026, 4, 8, 9, 20),
            datetime(2026, 4, 8, 9, 30),
        ]
        for job_id, finished_at in zip(created_ids, timestamps):
            job = session.get(CollectionJob, UUID(job_id))
            assert job is not None
            job.status = "success"
            job.started_at = finished_at
            job.finished_at = finished_at
        session.commit()

    response = client.get("/")

    assert response.status_code == 200
    assert response.text.count("<a class='recent-job-item'") == 3
    assert created_ids[3] in response.text
    assert created_ids[2] in response.text
    assert created_ids[1] in response.text
    assert created_ids[0] not in response.text
    assert "采集时间" in response.text
    assert "2026-04-08 09:30" in response.text
    assert response.text.index(created_ids[3]) < response.text.index(created_ids[2]) < response.text.index(created_ids[1])


def _run_job_and_wait_for_report(client, *, max_attempts: int = 20) -> tuple[str, str]:
    response = client.post("/jobs/run", follow_redirects=False)
    job_id = response.headers["location"].rsplit("/", 1)[-1]

    for _ in range(max_attempts):
        job_response = client.get(f"/api/jobs/{job_id}")
        body = job_response.json()
        report_id = body["report_id"]
        if body["status"] == "success" and report_id is not None:
            return job_id, report_id
        time.sleep(0.05)

    raise AssertionError(f"job {job_id} did not finish successfully")


def test_run_job_starts_background_execution_and_reaches_success(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "reports"))
    html_path = Path(tmp_path) / "topics.html"
    html_path.write_text(HTML_SOURCE, encoding="utf-8")
    client = create_test_client(make_sqlite_url(tmp_path, "pages-background.db"))
    client.post(
        "/api/sources",
        json={
            "name": "Local HTML",
            "site_name": "Local",
            "entry_url": html_path.resolve().as_uri(),
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 10,
            "enabled": True,
        },
    )

    response = client.post("/jobs/run", follow_redirects=False)

    assert response.status_code == 303
    job_path = response.headers["location"]
    job_id = job_path.rsplit("/", 1)[-1]

    final_status = None
    report_id = None
    for _ in range(20):
        job_response = client.get(f"/api/jobs/{job_id}")
        body = job_response.json()
        final_status = body["status"]
        report_id = body["report_id"]
        if final_status == "success" and report_id is not None:
            break
        time.sleep(0.05)

    assert final_status == "success"
    assert report_id is not None
    detail_page = client.get(f"/jobs/{job_id}")
    assert detail_page.status_code == 200
    assert report_id in detail_page.text
    assert f"/api/reports/{report_id}/download?format=md" in detail_page.text


def test_job_detail_uses_same_global_report_for_any_job(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "reports"))
    html_path = Path(tmp_path) / "topics.html"
    html_path.write_text(HTML_SOURCE, encoding="utf-8")
    client = create_test_client(make_sqlite_url(tmp_path, "pages-global-report.db"))
    client.post(
        "/api/sources",
        json={
            "name": "Local HTML",
            "site_name": "Local",
            "entry_url": html_path.resolve().as_uri(),
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 10,
            "enabled": True,
        },
    )

    first_job_id, first_report_id = _run_job_and_wait_for_report(client)
    second_job_id, second_report_id = _run_job_and_wait_for_report(client)

    first_detail = client.get(f"/jobs/{first_job_id}")
    second_detail = client.get(f"/jobs/{second_job_id}")

    assert first_report_id == second_report_id
    assert first_detail.status_code == 200
    assert second_detail.status_code == 200
    assert f"/reports/{first_report_id}" in first_detail.text
    assert f"/reports/{first_report_id}" in second_detail.text


def test_sources_page_lists_sources_and_actions(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-sources.db"))
    client.post(
        "/api/sources",
        json={
            "name": "NGA Hot",
            "site_name": "NGA",
            "entry_url": "https://example.com/nga",
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 30,
            "enabled": True,
            "source_group": "domestic",
        },
    )

    response = client.get("/sources")

    assert response.status_code == 200
    assert "采集源管理" in response.text
    assert "body class='app-shell theme-dark'" in response.text
    assert "app-shell" in response.text
    assert "page-header" in response.text
    assert "国内采集源" in response.text
    assert "国外采集源" in response.text
    assert "未分组采集源" in response.text
    assert "resource-card" in response.text
    assert "source-group-section" in response.text
    assert "source-group-header" in response.text
    assert "source-group-count" in response.text
    assert "NGA Hot" in response.text
    assert "编辑" in response.text
    assert "/sources/" in response.text


def test_source_edit_page_shows_common_edit_fields(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-source-edit.db"))
    created = client.post(
        "/api/sources",
        json={
            "name": "NGA Hot",
            "site_name": "NGA",
            "entry_url": "https://example.com/nga",
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 30,
            "enabled": True,
            "source_group": "domestic",
        },
    ).json()

    response = client.get(f"/sources/{created['id']}")

    assert response.status_code == 200
    assert "编辑采集源" in response.text
    assert "name='name'" in response.text
    assert "name='entry_url'" in response.text
    assert "name='search_keyword'" in response.text
    assert "name='source_group'" in response.text
    assert "name='schedule_group'" in response.text
    assert "name='max_items'" in response.text
    assert "name='enabled'" in response.text
    assert "source-config-grid" in response.text
    assert "source-field-full" in response.text
    assert "source-actions-row" in response.text
    assert "国内用于“立即采集国内”，国外用于“立即采集国外”" in response.text
    assert "name='fetch_mode'" not in response.text
    assert "name='list_selector'" not in response.text


def test_saving_source_edit_updates_source_and_redirects_to_sources_list(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-source-edit-save.db"))
    created = client.post(
        "/api/sources",
        json={
            "name": "NGA Hot",
            "site_name": "NGA",
            "entry_url": "https://example.com/nga",
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 30,
            "enabled": True,
            "source_group": "domestic",
        },
    ).json()

    response = client.post(
        f"/sources/{created['id']}",
        data={
            "name": "NGA Hot Edited",
            "entry_url": "https://example.com/nga-updated",
            "search_keyword": "",
            "source_group": "overseas",
            "schedule_group": "evening",
            "max_items": "15",
            "enabled": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/sources?source_saved=1"

    updated = client.get("/api/sources").json()[0]
    assert updated["name"] == "NGA Hot Edited"
    assert updated["entry_url"] == "https://example.com/nga-updated"
    assert updated["source_group"] == "overseas"
    assert updated["schedule_group"] == "evening"
    assert updated["max_items"] == 15
    assert updated["enabled"] is False


def test_sources_page_shows_source_saved_message(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-source-saved-banner.db"))

    response = client.get("/sources?source_saved=1")

    assert response.status_code == 200
    assert "采集源已更新" in response.text


def test_scheduler_page_shows_back_to_home_button(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-scheduler-back-home.db"))

    response = client.get("/scheduler")

    assert response.status_code == 200
    assert "返回首页" in response.text
    assert "href='/'" in response.text


def test_scheduler_page_shows_settings_panel(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOT_RUNTIME_ROOT", str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-scheduler.db"))

    response = client.get("/scheduler")

    assert response.status_code == 200
    assert "定时调度" in response.text
    assert "body class='app-shell theme-dark'" in response.text
    assert "app-shell" in response.text
    assert "scheduler-settings-panel" in response.text
    assert "name='daily_time'" in response.text
    assert "兼容旧版默认时间" in response.text
    assert "实际调度以“调度计划”列表为准" in response.text
    assert "启用钉钉群通知" in response.text
    assert "name='webhook'" in response.text
    assert str(get_runtime_paths(tmp_path).env_file) in response.text




def test_saving_dingtalk_settings_updates_runtime_app_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-dingtalk-settings.db"))

    response = client.post(
        '/scheduler/dingtalk',
        data={
            'enabled': 'true',
            'webhook': 'https://oapi.dingtalk.com/robot/send?access_token=test-token',
            'secret': 'SECdemo',
            'keyword': '热点报告',
        },
        follow_redirects=False,
    )

    env_file = get_runtime_paths(tmp_path).env_file
    env_text = env_file.read_text(encoding='utf-8')

    assert response.status_code == 303
    assert response.headers['location'] == '/scheduler'
    assert 'ENABLE_DINGTALK_NOTIFIER=true' in env_text
    assert 'DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=test-token' in env_text
    assert 'DINGTALK_SECRET=SECdemo' in env_text
    assert 'DINGTALK_KEYWORD=热点报告' in env_text

def test_new_source_page_shows_simplified_source_form_fields(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-source-form.db"))

    response = client.get("/sources/new")

    assert response.status_code == 200
    assert "新增采集源" in response.text
    assert "body class='app-shell theme-dark'" in response.text
    assert "app-shell" in response.text
    assert "form-panel" in response.text
    assert "name='entry_url'" in response.text
    assert "name='search_keyword'" in response.text
    assert "name='source_group'" in response.text
    assert "name='schedule_group'" in response.text
    assert "name='max_items'" in response.text
    assert "当前支持平台：Bilibili / X / YouTube" in response.text
    assert "class='form-control'" in response.text
    assert "source-config-grid" in response.text
    assert "source-field-full" in response.text
    assert "source-actions-row" in response.text
    assert "source-wizard" in response.text
    assert "第 1 步" in response.text
    assert "第 2 步" in response.text
    assert "<option value='domestic' selected>国内</option>" in response.text
    assert "国内用于“立即采集国内”，国外用于“立即采集国外”" in response.text
    assert "https://space.bilibili.com/20411266" in response.text
    assert "name='name'" not in response.text
    assert "name='list_selector'" not in response.text
    assert "name='include_keywords'" not in response.text
    assert "name='fetch_mode'" not in response.text


def test_post_run_domestic_job_redirects_to_job_detail_page(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-run-domestic.db"))
    client.post(
        "/api/sources",
        json={
            "name": "国内来源",
            "site_name": "NGA",
            "entry_url": "https://example.com/domestic",
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 30,
            "enabled": True,
            "source_group": "domestic",
        },
    )

    response = client.post("/jobs/run/domestic", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/jobs/")


def test_post_run_overseas_job_redirects_to_job_detail_page(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-run-overseas.db"))
    client.post(
        "/api/sources",
        json={
            "name": "国外来源",
            "site_name": "YouTube",
            "entry_url": "https://example.com/overseas",
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 30,
            "enabled": True,
            "source_group": "overseas",
        },
    )

    response = client.post("/jobs/run/overseas", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/jobs/")


def test_post_run_schedule_group_job_redirects_to_job_detail_page(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-run-schedule-group.db"))
    client.post(
        "/api/sources",
        json={
            "name": "晨报来源",
            "site_name": "Bilibili",
            "entry_url": "https://example.com/morning",
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 30,
            "enabled": True,
            "source_group": "domestic",
            "schedule_group": "morning",
        },
    )

    response = client.post("/jobs/run/schedule-group/morning", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/jobs/")


def test_post_run_schedule_group_job_without_sources_does_not_create_empty_job(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-run-schedule-group-empty.db"))

    response = client.post("/jobs/run/schedule-group/morning", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/?run_schedule_group_empty=morning"


def test_job_detail_page_shows_schedule_group_scope_label(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-detail-schedule-group-scope.db"))
    client.post(
        "/api/sources",
        json={
            "name": "晨报来源",
            "site_name": "Bilibili",
            "entry_url": "https://example.com/morning",
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 30,
            "enabled": True,
            "schedule_group": "morning",
        },
    )

    run_response = client.post("/jobs/run/schedule-group/morning", follow_redirects=False)
    job_id = run_response.headers["location"].rsplit("/", 1)[-1]
    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    assert "执行范围：调度分组 morning" in response.text


def test_post_run_domestic_job_without_sources_does_not_create_empty_job(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-run-domestic-empty.db"))

    response = client.post("/jobs/run/domestic", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/?run_group_empty=domestic"

    with SessionFactoryHolder.factory() as session:
        jobs = list(session.scalars(select(CollectionJob)).all())

    assert jobs == []


def test_job_progress_partial_renders_updated_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "reports"))
    html_path = Path(tmp_path) / "topics.html"
    html_path.write_text(HTML_SOURCE, encoding="utf-8")
    client = create_test_client(make_sqlite_url(tmp_path, "pages-progress.db"))
    client.post(
        "/api/sources",
        json={
            "name": "Local HTML",
            "site_name": "Local",
            "entry_url": html_path.resolve().as_uri(),
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 10,
            "enabled": True,
        },
    )
    response = client.post("/jobs/run", follow_redirects=False)
    job_id = response.headers["location"].rsplit("/", 1)[-1]

    body = ""
    for _ in range(20):
        progress_response = client.get(f"/jobs/{job_id}/progress")
        body = progress_response.text
        if "success" in body:
            break
        time.sleep(0.05)

    assert progress_response.status_code == 200
    assert "progress-panel" in body
    assert "总来源" in body
    assert "success" in body


def test_job_logs_partial_renders_error_message(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "reports"))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-logs.db"))
    client.post(
        "/api/sources",
        json={
            "name": "Broken Source",
            "site_name": "Broken",
            "entry_url": BROKEN_HTML_SOURCE,
            "fetch_mode": "http",
            "parser_type": "generic_css",
            "list_selector": ".topic",
            "title_selector": ".topic-link",
            "link_selector": ".topic-link",
            "meta_selector": ".topic-time",
            "include_keywords": ["新游"],
            "exclude_keywords": [],
            "max_items": 10,
            "enabled": True,
        },
    )
    response = client.post("/jobs/run", follow_redirects=False)
    job_id = response.headers["location"].rsplit("/", 1)[-1]

    body = ""
    for _ in range(20):
        log_response = client.get(f"/jobs/{job_id}/logs/view")
        body = log_response.text
        if "error" in body.lower():
            break
        time.sleep(0.05)

    assert log_response.status_code == 200
    assert "job-log-list" in body
    assert "error" in body.lower()


def test_job_progress_partial_highlights_source_configuration_error(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-config-error.db"))
    created = client.post("/api/jobs").json()
    job_id = UUID(created["id"])

    with SessionFactoryHolder.factory() as session:
        job = session.get(CollectionJob, job_id)
        job.status = "failed"
        job.failed_sources = 1
        session.add(
            JobLog(
                job_id=job.id,
                level="error",
                message="来源 URL 无效: https://www.youtube.com/@Missing/videos（页面不存在或频道不存在）",
            )
        )
        session.commit()

    response = client.get(f"/jobs/{created['id']}/progress")

    assert response.status_code == 200
    assert "来源配置错误" in response.text
    assert "来源 URL 无效" in response.text








def test_job_detail_page_shows_diagnostic_summary(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-diagnostics.db"))
    created = client.post("/api/jobs").json()
    job_id = UUID(created["id"])

    with SessionFactoryHolder.factory() as session:
        job = session.get(CollectionJob, job_id)
        job.status = "partial_success"
        job.failed_sources = 1
        session.add_all(
            [
                JobLog(
                    job_id=job.id,
                    level="error",
                    message="bilibili profile page hit risk control (风控); 请稍后重试或刷新 BILIBILI_COOKIE",
                ),
                JobLog(
                    job_id=job.id,
                    level="warning",
                    message="dingtalk notification skipped: DINGTALK_WEBHOOK is empty",
                ),
            ]
        )
        session.commit()

    response = client.get(f"/jobs/{created['id']}")

    assert response.status_code == 200
    assert "诊断摘要" in response.text
    assert "B站风控" in response.text
    assert "钉钉通知未发送" in response.text
    assert "未配置钉钉机器人 Webhook，请到调度页填写后再试。" in response.text


def test_job_progress_partial_shows_diagnostic_summary(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-progress-diagnostics.db"))
    created = client.post("/api/jobs").json()
    job_id = UUID(created["id"])

    with SessionFactoryHolder.factory() as session:
        job = session.get(CollectionJob, job_id)
        job.status = "failed"
        job.failed_sources = 1
        session.add_all(
            [
                JobLog(
                    job_id=job.id,
                    level="error",
                    message="bilibili profile page requires login (登录失效); 请刷新 BILIBILI_COOKIE",
                ),
                JobLog(
                    job_id=job.id,
                    level="warning",
                    message="dingtalk notification failed: errcode=310000, errmsg=keywords not in content",
                ),
            ]
        )
        session.commit()

    response = client.get(f"/jobs/{created['id']}/progress")

    assert response.status_code == 200
    assert "诊断摘要" in response.text
    assert "B站登录失效" in response.text
    assert "钉钉通知失败" in response.text
    assert "钉钉机器人已拒收消息，请检查机器人关键词配置是否与系统填写一致。" in response.text


def test_job_detail_page_humanizes_dingtalk_skip_for_no_new_items(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-dingtalk-no-new-items.db"))
    created = client.post("/api/jobs").json()
    job_id = UUID(created["id"])

    with SessionFactoryHolder.factory() as session:
        job = session.get(CollectionJob, job_id)
        job.status = "success"
        session.add(
            JobLog(
                job_id=job.id,
                level="warning",
                message="dingtalk notification skipped: no new collected items in current job",
            )
        )
        session.commit()

    response = client.get(f"/jobs/{created['id']}")

    assert response.status_code == 200
    assert "钉钉通知未发送" in response.text
    assert "本轮无新增内容，已跳过钉钉通知。" in response.text


def test_job_progress_partial_humanizes_dingtalk_skip_for_no_new_items(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "pages-progress-dingtalk-no-new-items.db"))
    created = client.post("/api/jobs").json()
    job_id = UUID(created["id"])

    with SessionFactoryHolder.factory() as session:
        job = session.get(CollectionJob, job_id)
        job.status = "success"
        session.add(
            JobLog(
                job_id=job.id,
                level="warning",
                message="dingtalk notification skipped: no new collected items in current job",
            )
        )
        session.commit()

    response = client.get(f"/jobs/{created['id']}/progress")

    assert response.status_code == 200
    assert "钉钉通知未发送" in response.text
    assert "本轮无新增内容，已跳过钉钉通知。" in response.text



def test_scheduler_page_shows_network_settings_panel(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-network-settings.db"))

    response = client.get('/scheduler')

    assert response.status_code == 200
    assert '站点网络访问' in response.text
    assert "name='proxy_enabled'" in response.text
    assert "name='outbound_proxy_url'" in response.text
    assert "name='bypass_domains'" in response.text


def test_saving_network_settings_updates_runtime_app_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-network-save.db"))

    response = client.post(
        '/scheduler/network',
        data={
            'proxy_enabled': 'true',
            'outbound_proxy_url': 'http://127.0.0.1:7890',
            'bypass_domains': 'bilibili.com,hdslb.com,bilivideo.com',
        },
        follow_redirects=False,
    )

    env_file = get_runtime_paths(tmp_path).env_file
    env_text = env_file.read_text(encoding='utf-8')

    assert response.status_code == 303
    assert response.headers['location'] == '/scheduler'
    assert 'ENABLE_SITE_PROXY_RULES=true' in env_text
    assert 'OUTBOUND_PROXY_URL=http://127.0.0.1:7890' in env_text
    assert 'OUTBOUND_PROXY_BYPASS_DOMAINS=bilibili.com,hdslb.com,bilivideo.com' in env_text


def test_scheduler_page_shows_fetch_interval_settings_panel(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-fetch-interval-settings.db"))

    response = client.get('/scheduler')

    assert response.status_code == 200
    assert '采集节流' in response.text
    assert "name='source_fetch_interval_seconds'" in response.text
    assert "name='bilibili_source_interval_seconds'" in response.text
    assert "name='bilibili_retry_delay_seconds'" in response.text


def test_saving_fetch_interval_settings_updates_runtime_app_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-fetch-interval-save.db"))

    response = client.post(
        '/scheduler/fetch-interval',
        data={
            'source_fetch_interval_seconds': '3',
            'bilibili_source_interval_seconds': '12',
            'bilibili_retry_delay_seconds': '7',
        },
        follow_redirects=False,
    )

    env_file = get_runtime_paths(tmp_path).env_file
    env_text = env_file.read_text(encoding='utf-8')

    assert response.status_code == 303
    assert response.headers['location'] == '/scheduler'
    assert 'SOURCE_FETCH_INTERVAL_SECONDS=3' in env_text
    assert 'BILIBILI_SOURCE_INTERVAL_SECONDS=12' in env_text
    assert 'BILIBILI_RETRY_DELAY_SECONDS=7' in env_text

def test_scheduler_page_shows_bilibili_cookie_settings_panel(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-bilibili-settings.db"))

    response = client.get('/scheduler')

    assert response.status_code == 200
    assert 'B站登录态' in response.text
    assert "name='bilibili_cookie'" in response.text
    assert '/scheduler/bilibili' in response.text
    assert '/scheduler/bilibili/browser-login' in response.text


def test_scheduler_page_shows_bilibili_success_message(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-bilibili-success-banner.db"))

    response = client.get('/scheduler?bilibili_saved=1')

    assert response.status_code == 200
    assert 'B站登录态已更新' in response.text


def test_scheduler_page_shows_bilibili_browser_sync_success_message(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-bilibili-browser-success-banner.db"))

    response = client.get('/scheduler?bilibili_browser_saved=1')

    assert response.status_code == 200
    assert '已从浏览器同步最新B站登录态' in response.text


def test_saving_bilibili_cookie_updates_runtime_app_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-bilibili-save.db"))

    response = client.post(
        '/scheduler/bilibili',
        data={
            'bilibili_cookie': 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123',
        },
        follow_redirects=False,
    )

    env_file = get_runtime_paths(tmp_path).env_file
    env_text = env_file.read_text(encoding='utf-8')

    assert response.status_code == 303
    assert response.headers['location'] == '/scheduler?bilibili_saved=1'
    assert 'BILIBILI_COOKIE=SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123' in env_text


def test_saving_prefixed_bilibili_cookie_normalizes_before_writing_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-bilibili-prefixed.db"))

    response = client.post(
        '/scheduler/bilibili',
        data={
            'bilibili_cookie': 'BILIBILI_COOKIE=SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123',
        },
        follow_redirects=False,
    )

    env_text = get_runtime_paths(tmp_path).env_file.read_text(encoding='utf-8')

    assert response.status_code == 303
    assert response.headers['location'] == '/scheduler?bilibili_saved=1'
    assert 'BILIBILI_COOKIE=SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123' in env_text


def test_saving_invalid_bilibili_cookie_shows_error_without_writing_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-bilibili-invalid.db"))

    response = client.post(
        '/scheduler/bilibili',
        data={
            'bilibili_cookie': 'bili_jct=test-jct; DedeUserID=123',
        },
        follow_redirects=False,
    )

    env_file = get_runtime_paths(tmp_path).env_file

    assert response.status_code == 422
    assert 'Cookie 缺少 SESSDATA' in response.text
    assert "bili_jct=test-jct; DedeUserID=123" in response.text
    assert not env_file.exists() or 'BILIBILI_COOKIE=' not in env_file.read_text(encoding='utf-8')


def test_browser_login_sync_updates_runtime_app_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-bilibili-browser-sync.db"))

    class _FakeResult:
        cookie = 'SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123'

    from app.api import routes_pages

    monkeypatch.setattr(
        routes_pages.BilibiliBrowserAuthService,
        'login_and_sync',
        lambda self: _FakeResult(),
    )

    response = client.post('/scheduler/bilibili/browser-login', follow_redirects=False)

    assert response.status_code == 303
    assert response.headers['location'] == '/scheduler?bilibili_browser_saved=1'
    env_text = get_runtime_paths(tmp_path).env_file.read_text(encoding='utf-8')
    assert 'BILIBILI_COOKIE=SESSDATA=test-sess; bili_jct=test-jct; DedeUserID=123' in env_text


def test_browser_login_sync_shows_error_when_browser_login_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('HOT_RUNTIME_ROOT', str(tmp_path))
    client = create_test_client(make_sqlite_url(tmp_path, "pages-bilibili-browser-sync-error.db"))

    from app.api import routes_pages

    def _raise_error(self):
        raise RuntimeError('browser login timeout')

    monkeypatch.setattr(routes_pages.BilibiliBrowserAuthService, 'login_and_sync', _raise_error)

    response = client.post('/scheduler/bilibili/browser-login', follow_redirects=False)

    assert response.status_code == 422
    assert 'browser login timeout' in response.text
