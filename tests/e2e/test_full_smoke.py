"""TC-E2E-001~005 — 全链路冒烟测试骨架。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="TC-E2E-001~005 待实现：阶段 4 端到端冒烟落地后启用")


class TestFullSmoke:
    def test_first_launch_creates_db_and_serves_health(self) -> None:
        """TC-E2E-001: 空 runtime root 启动成功 + DB 创建 + /health 返回 200"""

    def test_full_pipeline_with_dingtalk_mock(self) -> None:
        """TC-E2E-002: 配置 → 试抓 → 任务 → 报告 → 钉钉 mock 全链路成功"""

    def test_upgrade_preserves_data(self) -> None:
        """TC-E2E-003: 升级前后配置/任务/报告全部保留"""

    def test_cancel_during_running_job(self) -> None:
        """TC-E2E-004: 启动后取消任务，最终 cancelled 无僵尸"""

    def test_concurrent_jobs_finalize_report(self) -> None:
        """TC-E2E-005: 多任务并发收尾，全局报告内容完整"""
