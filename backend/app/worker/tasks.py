"""Celery background tasks for ingestion and AI analysis."""
import asyncio
import logging

from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine in a Celery task (sync context)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="app.worker.tasks.ingest_test_run",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="ingestion",
)
def ingest_test_run(self, sentinel_dict: dict, minio_prefix: str):
    """
    Background task: parse Allure JSON + TestNG XML from MinIO and
    upsert structured data into PostgreSQL + MongoDB.
    """
    from app.models.schemas import SentinelFile
    from app.services.ingestion import process_sentinel

    logger.info(f"[Task {self.request.id}] Starting ingestion: {sentinel_dict}")
    try:
        sentinel = SentinelFile(**sentinel_dict)
        _run_async(process_sentinel(sentinel, minio_prefix))
        logger.info(f"[Task {self.request.id}] Ingestion complete")
    except Exception as exc:
        logger.error(f"[Task {self.request.id}] Ingestion failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.worker.tasks.run_ai_analysis",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue="ai_analysis",
    time_limit=180,
)
def run_ai_analysis(self, test_case_id: str, test_name: str, **kwargs):
    """
    Background task: run the LangChain ReAct agent for a single test case.
    Used by the auto-analyzer to process failed tests without user interaction.
    """
    from app.services.agent import run_triage_agent

    logger.info(f"[Task {self.request.id}] AI analysis for: {test_name}")
    try:
        result = _run_async(run_triage_agent(
            test_case_id=test_case_id,
            test_name=test_name,
            **kwargs,
        ))
        logger.info(f"[Task {self.request.id}] Analysis complete. Confidence: {result.get('confidence_score')}")
        return result
    except Exception as exc:
        logger.error(f"[Task {self.request.id}] AI analysis failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.worker.tasks.take_coverage_snapshot",
    queue="default",
)
def take_coverage_snapshot():
    """Scheduled task: capture daily coverage snapshot for all active projects."""
    from sqlalchemy import select
    from app.db.postgres import AsyncSessionLocal
    from app.models.postgres import Project

    async def _run():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Project).where(Project.is_active.is_(True)))
            projects = result.scalars().all()
            logger.info(f"Taking coverage snapshot for {len(projects)} projects")
            # Coverage snapshot logic would go here
            # For now just log the intent
            for project in projects:
                logger.info(f"  Snapshot: {project.name}")

    logger.info("Running daily coverage snapshot task")
    _run_async(_run())
