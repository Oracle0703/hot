from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes_content import router as content_router
from app.api.routes_deliveries import router as deliveries_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_pages import configure_job_dispatcher, router as pages_router
from app.api.routes_reports import router as reports_router
from app.api.routes_site_accounts import router as site_accounts_router
from app.api.routes_sources import configure_session_factory, router as sources_router
from app.api.routes_subscriptions import router as subscriptions_router
from app.api.routes_system import (
    configure_session_factory as configure_system_session_factory,
    router as system_router,
)
from app.collectors.registry import CollectorRegistry
from app.config import get_settings
from app.db import create_session_factory, ensure_schema_compatibility, get_engine
from app.models.base import Base
from app.services.job_dispatcher import JobDispatcher
from app.services.scheduler_loop import SchedulerLoop
from app.services.source_execution_service import SourceExecutionService
from app.services.source_service import SourceService
from app.workers.runner import JobRunner
import app.models  # noqa: F401


def create_app(start_background_workers: bool = True) -> FastAPI:
    settings = get_settings()
    # 安装应用层日志轮转(REQ-SYS-101) — 启动早期挂载,失败不影响后续。
    try:
        from app.runtime_paths import get_runtime_paths
        from app.services.log_setup import setup_app_logging
        setup_app_logging(get_runtime_paths())
    except Exception:  # pragma: no cover - 启动期最大努力
        pass
    engine = get_engine()
    session_factory = create_session_factory(engine=engine)
    configure_session_factory(session_factory)
    configure_system_session_factory(session_factory)

    execution_service = SourceExecutionService(CollectorRegistry())
    dispatcher = JobDispatcher(JobRunner(session_factory=session_factory, source_executor=execution_service.execute))
    configure_job_dispatcher(dispatcher)

    scheduler_loop = None
    if start_background_workers and settings.enable_scheduler:
        scheduler_loop = SchedulerLoop(
            session_factory=session_factory,
            job_dispatcher=dispatcher,
            poll_interval_seconds=settings.scheduler_poll_seconds,
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        Base.metadata.create_all(bind=engine)
        ensure_schema_compatibility(engine)
        if start_background_workers:
            with session_factory() as session:
                SourceService(session).seed_default_sources()

        if scheduler_loop is not None:
            scheduler_loop.start()
        try:
            yield
        finally:
            if scheduler_loop is not None:
                scheduler_loop.stop()

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.state.scheduler_loop = scheduler_loop
    app.include_router(content_router)
    app.include_router(deliveries_router)
    app.include_router(site_accounts_router)
    app.include_router(sources_router)
    app.include_router(jobs_router)
    app.include_router(reports_router)
    app.include_router(subscriptions_router)
    app.include_router(pages_router)
    app.include_router(system_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
