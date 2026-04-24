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
