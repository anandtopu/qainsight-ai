from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.deps import get_current_active_user
from app.routers import (
    agents,
    analyze,
    analytics,
    auth,
    chat,
    deep_investigation,
    debug,
    feedback,
    integrations,
    live,
    metrics,
    notifications,
    projects,
    release_readiness,
    releases,
    reports,
    runs,
    search,
    stream,
    test_management,
    webhooks,
)
from app.routers.health import router as health_router
from app.routers.observability import router as observability_router


PUBLIC_ROUTERS: Sequence[APIRouter] = (
    auth.router,
    webhooks.router,
    stream.router,
    observability_router,
    health_router,
)

PROTECTED_ROUTERS: Sequence[APIRouter] = (
    projects.router,
    runs.router,
    metrics.router,
    search.router,
    analyze.router,
    analytics.router,
    integrations.router,
    notifications.router,
    live.router,
    agents.router,
    chat.router,
    feedback.router,
    deep_investigation.router,
    release_readiness.router,
    releases.router,
    reports.router,
    test_management.router,
)


def configure_middlewares(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Webhook-Secret", "X-Request-ID"],
    )

    # Import locally so middleware setup stays close to other app wiring.
    from app.middleware.telemetry import TelemetryMiddleware

    app.add_middleware(TelemetryMiddleware)


def configure_metrics(app: FastAPI) -> None:
    if not settings.METRICS_ENABLED:
        return

    from prometheus_fastapi_instrumentator import Instrumentator  # type: ignore

    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health/live", "/health/ready"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


def register_routers(app: FastAPI) -> None:
    for router in PUBLIC_ROUTERS:
        app.include_router(router)

    protected_deps = [Depends(get_current_active_user)]
    for router in PROTECTED_ROUTERS:
        app.include_router(router, dependencies=protected_deps)

    app.include_router(
        debug.router,
        prefix="/api/v1/debug",
        tags=["Debug"],
        dependencies=protected_deps,
    )
