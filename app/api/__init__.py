from app.api.routes_jobs import router as jobs_router
from app.api.routes_pages import router as pages_router
from app.api.routes_reports import router as reports_router
from app.api.routes_sources import router as sources_router

__all__ = ["jobs_router", "pages_router", "reports_router", "sources_router"]
