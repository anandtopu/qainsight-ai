"""
QA Insight AI — FastAPI Application Entry Point
"""
import logging
from contextlib import asynccontextmanager

import structlog  # type: ignore
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.deps import get_current_active_user
from app.db.mongo import close_mongo, get_mongo_db
from app.db.postgres import close_db
from app.routers import analyze, analytics, auth, integrations, live, metrics, projects, runs, search, webhooks, debug

# ── Logging setup ─────────────────────────────────────────────
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle hooks."""
    # Startup
    logger.info(
        "QA Insight AI starting",
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
        llm_provider=settings.LLM_PROVIDER,
        llm_model=settings.LLM_MODEL,
        offline_mode=settings.AI_OFFLINE_MODE,
    )
    # Ensure MongoDB indexes exist
    db = get_mongo_db()
    try:
        await db["raw_allure_json"].create_index("test_case_id", unique=True, background=True)
        await db["ai_analysis_payloads"].create_index("test_case_id", background=True)
        await db["ocp_pod_events"].create_index("test_run_id", background=True)
        logger.info("MongoDB indexes verified")
    except Exception as e:
        logger.warning("Failed to create MongoDB indexes", error=str(e))

    yield  # Application runs here

    # Shutdown
    await close_db()
    await close_mongo()
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

# ── CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────
# Public / Debug
app.include_router(webhooks.router)
app.include_router(auth.router)
app.include_router(debug.router, prefix="/api/v1/debug", tags=["Debug"])

# Protected
protected_deps = [Depends(get_current_active_user)]

app.include_router(projects.router, dependencies=protected_deps)
app.include_router(runs.router, dependencies=protected_deps)
app.include_router(metrics.router, dependencies=protected_deps)
app.include_router(search.router, dependencies=protected_deps)
app.include_router(analyze.router, dependencies=protected_deps)
app.include_router(analytics.router, dependencies=protected_deps)
app.include_router(integrations.router, dependencies=protected_deps)
app.include_router(live.router, dependencies=protected_deps)


# ── Health check ──────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
        "llm_provider": settings.LLM_PROVIDER,
        "offline_mode": settings.AI_OFFLINE_MODE,
    }


@app.get("/", tags=["System"])
async def root():
    return JSONResponse({
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    })
