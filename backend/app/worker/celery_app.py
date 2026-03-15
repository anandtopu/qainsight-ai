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
        "app.worker.tasks.*": {"queue": "default"},
    },
    beat_schedule={
        "daily-coverage-snapshot": {
            "task": "app.worker.tasks.take_coverage_snapshot",
            "schedule": crontab(hour=0, minute=5),
        },
    },
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
