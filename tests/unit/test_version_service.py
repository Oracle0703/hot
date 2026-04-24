"""TC-SYS-001~004 — version_service unit tests.

See docs/specs/50-system-and-ops.md and docs/test-cases.md.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from app.services import version_service
from app.services.version_service import get_version_info


def _write_version_file(tmp_path: Path, content: str) -> None:
    (tmp_path / "VERSION").write_text(content, encoding="utf-8")


def test_version_file_present_returns_declared_values(tmp_path, monkeypatch) -> None:
    """TC-SYS-001: VERSION 文件存在时返回声明的版本/commit/built_at"""
    _write_version_file(
        tmp_path,
        "version=9.9.9\ncommit=abc1234\nbuilt_at=2026-04-23T10:22:31+08:00\nchannel=offline\n",
    )
    monkeypatch.setenv("HOT_RUNTIME_ROOT", str(tmp_path))

    info = get_version_info()

    assert info.version == "9.9.9"
    assert info.commit == "abc1234"
    assert info.built_at == "2026-04-23T10:22:31+08:00"
    assert info.channel == "offline"
    assert info.python_version  # 非空
    assert Path(info.runtime_root) == tmp_path
    assert info.uptime_seconds >= 0


def test_version_file_missing_falls_back_to_dev_unknown(tmp_path, monkeypatch) -> None:
    """TC-SYS-003: VERSION 与 git 都缺失时返回 dev-unknown"""
    monkeypatch.setenv("HOT_RUNTIME_ROOT", str(tmp_path))
    # 屏蔽 git 调用
    monkeypatch.setattr(version_service, "_git_short_commit", lambda: "")

    info = get_version_info()

    assert info.version == "dev-unknown"
    assert info.commit == "unknown"
    assert info.channel == "dev"


def test_uptime_increases_between_calls(tmp_path, monkeypatch) -> None:
    """TC-SYS-004: uptime_seconds 单调递增"""
    monkeypatch.setenv("HOT_RUNTIME_ROOT", str(tmp_path))
    first = get_version_info().uptime_seconds
    time.sleep(0.05)
    second = get_version_info().uptime_seconds

    assert second >= first


@pytest.mark.skipif(
    not Path(__file__).resolve().parents[2].joinpath(".git").exists(),
    reason="not a git checkout",
)
def test_version_file_missing_falls_back_to_git_commit(tmp_path, monkeypatch) -> None:
    """TC-SYS-002: VERSION 缺失但 git 仓库存在时 commit 不为 unknown"""
    # 让 runtime_root 指向真正的仓库根(git rev-parse 才能在那里工作),
    # 并通过不写 VERSION 来触发回退分支。
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("HOT_RUNTIME_ROOT", str(repo_root))
    info = get_version_info()
    assert info.commit and info.commit != "unknown"
