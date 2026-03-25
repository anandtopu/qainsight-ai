"""Celery application configuration."""
from celery import Celery  # type: ignore
from celery.schedules import crontab  # type: ignore

from app.core.config import settings

celery_app = Celery(
    "qainsight",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "app.worker.tasks.ingest_test_run": {"queue": "ingestion"},
        "app.worker.tasks.run_ai_analysis": {"queue": "ai_analysis"},
        "app.worker.tasks.run_agent_pipeline": {"queue": "ai_analysis"},
        "app.worker.tasks.*": {"queue": "default"},
    },
    beat_schedule={
        "daily-coverage-snapshot": {
            "task": "app.worker.tasks.take_coverage_snapshot",
            "schedule": crontab(hour=0, minute=5),
        },
    },
    # Prevent memory bloat from stale results
    result_expires=3600,            # expire task results after 1 hour
    # Worker reliability
    worker_prefetch_multiplier=1,   # one task at a time per worker (fair dispatch)
    task_acks_late=True,            # ack only after task completes (safe retries)
    worker_max_tasks_per_child=200, # recycle worker after 200 tasks (prevent memory leaks)
    # Time limits: soft warns the task, hard kills it
    task_soft_time_limit=540,       # 9 min soft (send SIGTERM to task)
    task_time_limit=660,            # 11 min hard (SIGKILL)
    # Connection resilience
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
)
