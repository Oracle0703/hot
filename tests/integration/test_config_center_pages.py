"""TC-API-101~103 — 配置中心页面集成测试。"""

from __future__ import annotations

import os

from tests.conftest import create_test_client, make_sqlite_url


def _client(tmp_path):
    os.environ["HOT_RUNTIME_ROOT"] = str(tmp_path)
    return create_test_client(make_sqlite_url(tmp_path, "config_center.db"))


def test_page_renders_each_group(tmp_path) -> None:
    """TC-API-101"""
    client = _client(tmp_path)
    resp = client.get("/config")
    assert resp.status_code == 200
    body = resp.text
    # 至少覆盖核心分组
    for label in ("app", "database", "scheduler", "dingtalk", "bilibili", "network", "weekly"):
        assert label in body, f"分组 {label} 未渲染"
    assert "/weekly" in body
    assert "WEEKLY_GRADE_PUSH_THRESHOLD" in body
    assert "周榜批量推送的人工评分阈值" in body


def test_invalid_value_returns_422(tmp_path) -> None:
    """TC-API-102"""
    client = _client(tmp_path)
    resp = client.post("/config", data={"SCHEDULER_POLL_SECONDS": "abc"})
    assert resp.status_code == 422
    assert "SCHEDULER_POLL_SECONDS" in resp.text


def test_valid_value_persists(tmp_path) -> None:
    """TC-API-103"""
    client = _client(tmp_path)
    resp = client.post("/config", data={"SCHEDULER_POLL_SECONDS": "120"})
    assert resp.status_code == 200
    env_path = tmp_path / "data" / "app.env"
    assert env_path.exists()
    text = env_path.read_text(encoding="utf-8-sig")
    assert "SCHEDULER_POLL_SECONDS=120" in text


def test_saving_weekly_values_shows_link_to_weekly_page_with_applied_summary(tmp_path) -> None:
    client = _client(tmp_path)

    resp = client.post(
        "/config",
        data={
            "WEEKLY_GRADE_PUSH_THRESHOLD": "A",
            "WEEKLY_COVER_CACHE_RETENTION_DAYS": "45",
        },
    )

    assert resp.status_code == 200
    assert "/weekly?config_updated=1" in resp.text
    assert "当前推送阈值：A" in resp.text
    assert "封面缓存保留：45 天" in resp.text


def test_weekly_return_context_is_preserved_in_config_center(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.get("/config?return_to=weekly")

    assert response.status_code == 200
    assert "action=\"/config?return_to=weekly\"" in response.text
    assert "href='/weekly'" in response.text


def test_saving_weekly_values_with_return_context_shows_back_to_weekly_cta(tmp_path) -> None:
    client = _client(tmp_path)

    resp = client.post(
        "/config?return_to=weekly",
        data={
            "WEEKLY_GRADE_PUSH_THRESHOLD": "S",
        },
    )

    assert resp.status_code == 200
    assert "/weekly?config_updated=1" in resp.text
    assert "返回最近一周热点" in resp.text
