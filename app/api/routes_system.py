"""System-level endpoints for ops staff.

Implements the v1 baseline described in ``docs/specs/50-system-and-ops.md``:
``/system/info``, ``/system/health/extended``, ``/system/jobs/cancel-running``,
``/system/config/export``.
"""

from __future__ import annotations

import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models.job import CollectionJob
from app.runtime_paths import get_runtime_paths
from app.services import cancel_registry
from app.services.version_service import get_version_info


router = APIRouter(prefix="/system", tags=["system"])


class _SessionFactoryHolder:
    factory: sessionmaker | None = None


def configure_session_factory(factory: sessionmaker) -> None:
    _SessionFactoryHolder.factory = factory


_SENSITIVE_KEYS = {
    "BILIBILI_COOKIE",
    "X_AUTH_TOKEN",
    "X_CT0",
    "DINGTALK_WEBHOOK",
    "DINGTALK_SECRET",
    "OUTBOUND_PROXY_URL",
    "DATABASE_URL",
    "CONFIG_ENCRYPTION_KEY",
}


def _mask_value(value: str) -> str:
    if not value:
        return ""
    if len(value) < 8:
        return "***"
    return f"{value[:4]}***{value[-4:]}"


def _settings_to_dict() -> dict[str, Any]:
    settings = get_settings()
    raw: dict[str, Any] = {}
    for field_name, value in asdict(settings).items():
        env_key = field_name.upper()
        raw[env_key] = value
    return raw


def _scheduler_state(request: Request) -> dict[str, Any]:
    scheduler_loop = getattr(request.app.state, "scheduler_loop", None)
    if scheduler_loop is None:
        return {"alive": False, "enabled": False}
    thread = getattr(scheduler_loop, "_thread", None)
    return {
        "alive": bool(thread and thread.is_alive()),
        "enabled": True,
        "poll_interval_seconds": scheduler_loop.poll_interval_seconds,
    }


def _check_database() -> tuple[bool, str | None]:
    factory = _SessionFactoryHolder.factory
    if factory is None:
        return False, "session_factory_not_configured"
    try:
        with factory() as session:
            session.execute(select(1))
        return True, None
    except SQLAlchemyError as exc:  # pragma: no cover - error path simple
        return False, exc.__class__.__name__


def _disk_free_mb() -> float:
    paths = get_runtime_paths()
    target = paths.data_dir if paths.data_dir.exists() else paths.runtime_root
    try:
        usage = shutil.disk_usage(str(target))
        return round(usage.free / (1024 * 1024), 2)
    except OSError:
        return -1.0


def _running_job_id() -> str | None:
    factory = _SessionFactoryHolder.factory
    if factory is None:
        return None
    try:
        with factory() as session:
            row = session.execute(
                select(CollectionJob.id).where(CollectionJob.status == "running").limit(1)
            ).first()
            if row is None:
                return None
            return str(row[0])
    except SQLAlchemyError:
        return None


@router.get("/info")
def system_info() -> dict[str, Any]:
    info = get_version_info()
    settings = get_settings()
    payload = asdict(info)
    payload["app_name"] = settings.app_name
    payload["app_env"] = settings.environment
    payload["debug"] = settings.debug
    return payload


@router.get("/health/extended")
def system_health_extended(request: Request, response: Response) -> dict[str, Any]:
    db_ok, db_reason = _check_database()
    scheduler = _scheduler_state(request)
    disk_free = _disk_free_mb()
    issues: list[dict[str, str]] = []

    if not db_ok:
        issues.append({"code": "DATABASE_UNREACHABLE", "severity": "error", "message": db_reason or "unknown"})
    if scheduler.get("enabled") and not scheduler.get("alive"):
        issues.append({"code": "SCHEDULER_NOT_RUNNING", "severity": "error", "message": "scheduler thread not alive"})
    if 0 <= disk_free < 200:
        issues.append({"code": "DISK_LOW", "severity": "warn", "message": f"data dir free {disk_free} MB"})

    payload = {
        "status": "ok" if not any(item["severity"] == "error" for item in issues) else "error",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "database": {"ok": db_ok, "reason": db_reason},
        "scheduler": scheduler,
        "disk": {"free_mb": disk_free},
        "running_job_id": _running_job_id(),
        "issues": issues,
    }
    if payload["status"] != "ok":
        response.status_code = 503
    return payload


@router.post("/jobs/cancel-running")
def cancel_running_job(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    force = bool((payload or {}).get("force", False))
    job_id = _running_job_id()
    if job_id is None:
        return {"cancelled_job_id": None, "reason": "no_running_job"}

    if cancel_registry.is_cancelled(job_id):
        return {
            "cancelled_job_id": job_id,
            "force": force,
            "reason": "already_cancelled",
        }

    requested_at = cancel_registry.request_cancel(job_id)
    # 协作式取消：JobRunner 在下一个 source 边界检测到后跳出，最终状态为 cancelled。
    # force=true 预留为阶段 4 的强制中断选项，本期徽章仅在响应中回传。
    return {
        "cancelled_job_id": job_id,
        "force": force,
        "requested_at": requested_at.isoformat(),
        "mode": "force" if force else "cooperative",
    }


@router.get("/config/export")
def export_config(mask: bool = Query(default=True)) -> Response:
    settings = get_settings()
    if not mask and not settings.debug:
        raise HTTPException(status_code=403, detail="mask=false 仅在 APP_DEBUG=true 时可用")

    rows: list[str] = []
    for key, value in sorted(_settings_to_dict().items()):
        text_value = "" if value is None else str(value)
        if mask and key in _SENSITIVE_KEYS:
            text_value = _mask_value(text_value)
        # quote strings that contain special characters
        if any(ch in text_value for ch in [":", "#", "\n"]) and not text_value.startswith('"'):
            text_value = '"' + text_value.replace('"', '\\"') + '"'
        rows.append(f"{key}: {text_value}")

    body = "\n".join(rows) + "\n"
    return Response(content=body, media_type="text/yaml")


@router.get("/metrics")
def system_metrics(window_hours: float = Query(default=24.0, gt=0, le=24 * 30)) -> dict[str, Any]:
    """REQ-OPS-003 — 任务成功率 / 时长分位数。"""
    from app.services.metrics_service import compute_job_metrics

    factory = _SessionFactoryHolder.factory
    if factory is None:
        raise HTTPException(status_code=503, detail="session_factory_not_configured")
    with factory() as session:
        metrics = compute_job_metrics(session, window_hours=window_hours)
    return metrics.to_dict()
