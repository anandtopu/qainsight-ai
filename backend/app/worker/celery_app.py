"""Celery application configuration."""
from celery import Celery  # type: ignore
from celery.schedules import crontab  # type: ignore
from kombu import Exchange, Queue  # type: ignore

from app.core.config import settings

celery_app = Celery(
    "qainsight",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.worker.tasks"],
)

# ── Priority queues ────────────────────────────────────────────────────────────
# critical  (9)  — live test analysis, immediate user-facing results
# ingestion (7)  — test report parsing from MinIO
# ai_analysis(5) — offline pipeline (anomaly, root-cause, summary)
# default   (1)  — notifications, snapshots, housekeeping

_default_exchange = Exchange("default", type="direct")

celery_app.conf.task_queues = (
    Queue("critical",    _default_exchange, routing_key="critical",    queue_arguments={"x-max-priority": 10}),
    Queue("ingestion",   _default_exchange, routing_key="ingestion",   queue_arguments={"x-max-priority": 10}),
    Queue("ai_analysis", _default_exchange, routing_key="ai_analysis", queue_arguments={"x-max-priority": 10}),
    Queue("default",     _default_exchange, routing_key="default",     queue_arguments={"x-max-priority": 10}),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
    task_routes={
        "app.worker.tasks.run_live_test_analysis": {"queue": "critical"},
        "app.worker.tasks.ingest_test_run":         {"queue": "ingestion"},
        "app.worker.tasks.run_ai_analysis":         {"queue": "ai_analysis"},
        "app.worker.tasks.run_agent_pipeline":      {"queue": "ai_analysis"},
        "app.worker.tasks.*":                       {"queue": "default"},
    },
    beat_schedule={
        "daily-coverage-snapshot": {
            "task": "app.worker.tasks.take_coverage_snapshot",
            "schedule": crontab(hour=0, minute=5),
        },
    },
    # Prevent memory bloat from stale results
    result_expires=3600,
    # Worker reliability
    worker_prefetch_multiplier=1,   # fair dispatch — one task at a time per slot
    task_acks_late=True,            # ack only after task completes (safe retries on crash)
    worker_max_tasks_per_child=200, # recycle worker process after 200 tasks (prevent leaks)
    # Time limits: soft sends SIGTERM to task coroutine, hard sends SIGKILL
    task_soft_time_limit=540,       # 9 min soft
    task_time_limit=660,            # 11 min hard
    # Connection resilience
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
)
