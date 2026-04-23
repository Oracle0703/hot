import time
from pathlib import Path

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


def _run_job_and_wait_for_report(client, *, max_attempts: int = 20) -> tuple[str, str]:
    run_response = client.post("/jobs/run", follow_redirects=False)
    job_id = run_response.headers["location"].rsplit("/", 1)[-1]

    report_id = None
    for _ in range(max_attempts):
        job_response = client.get(f"/api/jobs/{job_id}")
        body = job_response.json()
        report_id = body["report_id"]
        if body["status"] == "success" and report_id:
            return job_id, report_id
        time.sleep(0.05)

    raise AssertionError(f"job {job_id} did not finish successfully")


def test_reports_page_lists_generated_report_and_download_works(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "reports"))
    html_path = Path(tmp_path) / "topics.html"
    html_path.write_text(HTML_SOURCE, encoding="utf-8")
    client = create_test_client(make_sqlite_url(tmp_path, "reports-page.db"))
    client.post(
        "/api/sources",
        json={
            "name": "本地 HTML",
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

    run_response = client.post("/jobs/run", follow_redirects=False)
    job_id = run_response.headers["location"].rsplit("/", 1)[-1]

    report_id = None
    for _ in range(20):
        job_response = client.get(f"/api/jobs/{job_id}")
        body = job_response.json()
        report_id = body["report_id"]
        if body["status"] == "success" and report_id:
            break
        time.sleep(0.05)

    reports_page = client.get("/reports")
    assert reports_page.status_code == 200
    assert "历史报告" in reports_page.text
    assert "body class='app-shell theme-dark'" in reports_page.text
    assert "app-shell" in reports_page.text
    assert "panel" in reports_page.text
    assert report_id in reports_page.text

    report_detail = client.get(f"/reports/{report_id}")
    assert report_detail.status_code == 200
    assert "报告预览" in report_detail.text
    assert "body class='app-shell theme-dark'" in report_detail.text
    assert "app-shell" in report_detail.text
    assert "panel" in report_detail.text
    assert "重磅新游版号过审" in report_detail.text
    assert "返回首页" in report_detail.text
    assert "href='/'" in report_detail.text

    markdown_download = client.get(f"/api/reports/{report_id}/download?format=md")
    docx_download = client.get(f"/api/reports/{report_id}/download?format=docx")

    assert markdown_download.status_code == 200
    assert "重磅新游版号过审" in markdown_download.text
    assert docx_download.status_code == 200
    assert docx_download.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument")


def test_reports_page_shows_single_global_report_after_two_runs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "reports"))
    html_path = Path(tmp_path) / "topics.html"
    html_path.write_text(HTML_SOURCE, encoding="utf-8")
    client = create_test_client(make_sqlite_url(tmp_path, "reports-global-page.db"))
    client.post(
        "/api/sources",
        json={
            "name": "本地 HTML",
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

    _, first_report_id = _run_job_and_wait_for_report(client)
    _, second_report_id = _run_job_and_wait_for_report(client)

    reports_page = client.get("/reports")

    assert first_report_id == second_report_id
    assert reports_page.status_code == 200
    assert "全局热点总报告" in reports_page.text
    assert "body class='app-shell theme-dark'" in reports_page.text
    assert reports_page.text.count(f"href='/reports/{first_report_id}'") == 1
