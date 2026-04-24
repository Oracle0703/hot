"""Cooperative cancel registry.

JobRunner 在每个 source 边界、以及发布报告之前会调用 ``is_cancelled(job_id)`` 检查。
``/system/jobs/cancel-running`` 接口通过 ``request_cancel(job_id)`` 标记取消;
JobRunner 主循环检测到后跳出剩余 source,任务最终被标记为 ``cancelled``。

注:阶段 1 的 routes_system 是 stub;阶段 3.2 通过本注册表把语义打通。
强制取消(中断 inflight 调用)留作阶段 4 的 force=true 选项,本期默认协作式。
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID


_lock = threading.Lock()
_pending: dict[str, datetime] = {}


def _key(job_id: UUID | str) -> str:
    return str(job_id)


def request_cancel(job_id: UUID | str) -> datetime:
    """登记一次取消请求,返回时间戳。重复请求使用最新时间戳。"""
    now = datetime.now(timezone.utc)
    with _lock:
        _pending[_key(job_id)] = now
    return now


def is_cancelled(job_id: UUID | str) -> bool:
    with _lock:
        return _key(job_id) in _pending


def consume(job_id: UUID | str) -> bool:
    """JobRunner 完成 cancel 处理后调用,返回是否真的存在 pending。"""
    with _lock:
        return _pending.pop(_key(job_id), None) is not None


def clear() -> None:
    """测试夹具用。"""
    with _lock:
        _pending.clear()


def pending_job_ids() -> Iterable[str]:
    with _lock:
        return list(_pending.keys())
