"""
QA Insight AI — FastAPI Application Entry Point
"""
import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.mongo import close_mongo, get_mongo_db
from app.db.postgres import close_db, engine
from app.routers import analyze, integrations, metrics, projects, runs, search, webhooks

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
    await db["raw_allure_json"].create_index("test_case_id", unique=True, background=True)
    await db["ai_analysis_payloads"].create_index("test_case_id", background=True)
    await db["ocp_pod_events"].create_index("test_run_id", background=True)
    logger.info("MongoDB indexes verified")

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
app.include_router(webhooks.router)
app.include_router(projects.router)
app.include_router(runs.router)
app.include_router(metrics.router)
app.include_router(search.router)
app.include_router(analyze.router)
app.include_router(integrations.router)


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
