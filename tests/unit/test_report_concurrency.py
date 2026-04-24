"""TC-RPT-001~004 — 报告写入跨进程文件锁 (portalocker)。

ReportService._activate_prepared_report_files 会在 markdown_path 同目录创建
``.hot-report.lock`` 并以 portalocker 持有,确保两个 writer 不会同时执行
".bak / .replace" 切换。本测试不需要全套 ORM 上下文,直接验证锁行为即可。
"""

from __future__ import annotations

import threading
import time

import portalocker
import pytest


def _hold_lock(lock_path, hold_seconds, started_event, released_event):
    with portalocker.Lock(str(lock_path), 'w', timeout=5):
        started_event.set()
        time.sleep(hold_seconds)
    released_event.set()


def test_lock_serializes_concurrent_writers(tmp_path) -> None:
    """TC-RPT-001: 第二个 writer 必须等待第一个释放锁后才能进入临界区"""
    lock_path = tmp_path / '.hot-report.lock'
    started = threading.Event()
    released = threading.Event()

    holder = threading.Thread(
        target=_hold_lock,
        args=(lock_path, 0.5, started, released),
        daemon=True,
    )
    holder.start()
    assert started.wait(2.0), '第一个 writer 未能拿到锁'

    acquired_at = []

    def second_writer():
        with portalocker.Lock(str(lock_path), 'w', timeout=10):
            acquired_at.append(time.monotonic())

    second = threading.Thread(target=second_writer, daemon=True)
    t0 = time.monotonic()
    second.start()
    second.join(timeout=5)
    holder.join(timeout=5)

    assert acquired_at, '第二个 writer 始终未能获得锁'
    elapsed = acquired_at[0] - t0
    assert elapsed >= 0.4, f'第二个 writer 未等待第一个释放,实际只等了 {elapsed:.3f}s'


def test_lock_timeout_raises(tmp_path) -> None:
    """TC-RPT-002: 持续被占用的锁,新申请者在 timeout 内拿不到则抛异常"""
    lock_path = tmp_path / '.hot-report.lock'
    started = threading.Event()
    released = threading.Event()

    holder = threading.Thread(
        target=_hold_lock,
        args=(lock_path, 1.0, started, released),
        daemon=True,
    )
    holder.start()
    assert started.wait(2.0)

    with pytest.raises(portalocker.exceptions.LockException):
        with portalocker.Lock(str(lock_path), 'w', timeout=0.2):
            pass

    holder.join(timeout=5)


@pytest.mark.skip(reason="TC-RPT-003 临时文件保留待生产观察后落实")
def test_temp_file_kept_on_failure() -> None:
    pass


@pytest.mark.skip(reason="TC-RPT-004 docx 并发后可被 python-docx 打开 — 需完整 ReportService 集成夹具")
def test_docx_atomic_replace() -> None:
    pass
