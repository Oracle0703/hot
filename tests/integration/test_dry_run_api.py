"""TC-API-201~202 — 试抓接口集成测试。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.conftest import create_test_client, make_sqlite_url


@pytest.fixture(autouse=True)
def _allow_file_scheme(monkeypatch):
    monkeypatch.setenv("APP_DEBUG", "true")


def _write_html_fixture(tmp_path: Path) -> Path:
    fixture = tmp_path / "demo.html"
    rows = "".join(
        f'<li class="item"><span class="t">title-{i}</span><a href="https://x/{i}">go</a></li>'
        for i in range(8)
    )
    fixture.write_text(f"<html><body><ul>{rows}</ul></body></html>", encoding="utf-8")
    return fixture


def test_dry_run_unsaved_source(tmp_path) -> None:
    """TC-API-201"""
    fixture = _write_html_fixture(tmp_path)
    os.environ["HOT_RUNTIME_ROOT"] = str(tmp_path)
    client = create_test_client(make_sqlite_url(tmp_path, "dryrun.db"))
    payload = {
        "name": "tmp",
        "entry_url": fixture.as_uri(),
        "fetch_mode": "http",
        "list_selector": "li.item",
        "title_selector": ".t",
        "link_selector": "a",
        "include_keywords": [],
        "exclude_keywords": [],
        "max_items": 30,
    }
    resp = client.post("/api/sources/dry-run", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body and "diagnostics" in body
    assert len(body["items"]) <= 5
    assert body["diagnostics"]["list_hits"] >= 8


def test_dry_run_saved_source(tmp_path) -> None:
    """TC-API-202"""
    fixture = _write_html_fixture(tmp_path)
    os.environ["HOT_RUNTIME_ROOT"] = str(tmp_path)
    client = create_test_client(make_sqlite_url(tmp_path, "dryrun2.db"))
    payload = {
        "name": "saved",
        "entry_url": fixture.as_uri(),
        "fetch_mode": "http",
        "list_selector": "li.item",
        "title_selector": ".t",
        "link_selector": "a",
        "include_keywords": [],
        "exclude_keywords": [],
        "max_items": 30,
    }
    create_resp = client.post("/api/sources", json=payload)
    assert create_resp.status_code == 201, create_resp.text
    source_id = create_resp.json()["id"]

    resp = client.post(f"/api/sources/{source_id}/dry-run")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body and "diagnostics" in body
