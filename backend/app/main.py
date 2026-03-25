"""
QA Insight AI — FastAPI Application Entry Point
"""
import asyncio
import logging
from contextlib import asynccontextmanager

import structlog  # type: ignore
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler  # type: ignore
from slowapi.errors import RateLimitExceeded  # type: ignore
from slowapi.util import get_remote_address  # type: ignore

from app.core.config import settings
from app.core.deps import get_current_active_user
from app.db.mongo import close_mongo, get_mongo_db
from app.db.postgres import close_db
from app.db.redis_client import close_redis
from app.routers import agents, analyze, analytics, auth, chat, feedback, integrations, live, metrics, notifications, projects, runs, search, webhooks, debug

# ── Logging setup ─────────────────────────────────────────────
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = structlog.get_logger(__name__)

# ── Rate limiter (login brute-force protection) ───────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle hooks."""
    logger.info(
        "QA Insight AI starting",
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
    )
    # Ensure MongoDB indexes exist
    db = get_mongo_db()
    try:
        await db["raw_allure_json"].create_index("test_case_id", unique=True, background=True)
        await db["ai_analysis_payloads"].create_index("test_case_id", background=True)
        await db["ocp_pod_events"].create_index("test_run_id", background=True)
        await db["run_summaries"].create_index("test_run_id", unique=True, background=True)
        await db["live_execution_events"].create_index("run_id", background=True)
        logger.info("MongoDB indexes verified")
    except Exception as e:
        logger.warning("Failed to create MongoDB indexes", error=str(e))

    # Start live event stream consumer (reads from Redis Streams, dispatches to WebSocket)
    from app.streams.live_consumer import LiveEventStreamConsumer
    _consumer = LiveEventStreamConsumer()
    _consumer_task = asyncio.create_task(_consumer.run(), name="live-event-consumer")
    logger.info("Live event stream consumer started")

    yield  # Application runs here

    # Shutdown consumer
    _consumer_task.cancel()
    try:
        await _consumer_task
    except asyncio.CancelledError:
        pass
    logger.info("Live event stream consumer stopped")

    # Shutdown DB connections
    await close_db()
    await close_mongo()
    await close_redis()
    logger.info("QA Insight AI shutdown complete")


# ── Application factory ───────────────────────────────────────
app = FastAPI(
    title="QA Insight AI",
    description="360° AI-Powered Software Testing Intelligence Platform",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Webhook-Secret"],
)

# ── Routers ───────────────────────────────────────────────────
# Public
app.include_router(auth.router)

# Webhook — protected by X-Webhook-Secret header (see deps.verify_webhook_secret)
app.include_router(webhooks.router)

# Protected — require a valid JWT access token
protected_deps = [Depends(get_current_active_user)]

app.include_router(projects.router, dependencies=protected_deps)
app.include_router(runs.router, dependencies=protected_deps)
app.include_router(metrics.router, dependencies=protected_deps)
app.include_router(search.router, dependencies=protected_deps)
app.include_router(analyze.router, dependencies=protected_deps)
app.include_router(analytics.router, dependencies=protected_deps)
app.include_router(integrations.router, dependencies=protected_deps)
app.include_router(notifications.router, dependencies=protected_deps)
app.include_router(live.router, dependencies=protected_deps)
app.include_router(agents.router, dependencies=protected_deps)
app.include_router(chat.router, dependencies=protected_deps)
app.include_router(feedback.router, dependencies=protected_deps)

# Debug — ADMIN only (role check applied at endpoint level in debug.py)
app.include_router(debug.router, prefix="/api/v1/debug", tags=["Debug"], dependencies=protected_deps)


# ── Login rate limit (applied here to avoid importing limiter into auth.py) ──
@app.middleware("http")
async def rate_limit_login(request: Request, call_next):
    """Apply 10 requests/minute rate limit to the login endpoint."""
    if request.url.path == "/api/v1/auth/login" and request.method == "POST":

        @limiter.limit("10/minute")
        async def _limited(request: Request):
            pass

        try:
            await _limited(request)
        except RateLimitExceeded:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many login attempts. Try again in a minute."},
            )
    return await call_next(request)


# ── Health check ──────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/", tags=["System"])
async def root():
    return JSONResponse({
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    })
