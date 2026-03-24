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
    name="app.worker.tasks.dispatch_run_notifications",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    queue="default",
)
def dispatch_run_notifications(
    self,
    project_id: str,
    run_id: str,
    build_number: str,
    pass_rate: float,
    total_tests: int,
    failed_tests: int,
    project_name: str,
    dashboard_url: str = "#",
):
    """Background task: fan-out run-completion notifications to all subscribed users."""
    import uuid as _uuid
    from app.services.notification.manager import dispatch_run_notifications as _dispatch

    logger.info("[Task %s] Dispatching run notifications for build=%s", self.request.id, build_number)
    try:
        _run_async(_dispatch(
            project_id=_uuid.UUID(project_id),
            run_id=_uuid.UUID(run_id),
            build_number=build_number,
            pass_rate=pass_rate,
            total_tests=total_tests,
            failed_tests=failed_tests,
            project_name=project_name,
            dashboard_url=dashboard_url,
        ))
    except Exception as exc:
        logger.error("[Task %s] Notification dispatch failed: %s", self.request.id, exc, exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.worker.tasks.run_agent_pipeline",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    queue="ai_analysis",
    time_limit=600,
)
def run_agent_pipeline(
    self,
    test_run_id: str,
    project_id: str,
    build_number: str,
    workflow_type: str = "offline",
):
    """
    Background task: run the full multi-agent pipeline for a completed test run.
    Stages: ingestion → anomaly detection → root-cause analysis → summary → triage
    """
    from app.agents.workflow import run_offline_pipeline

    logger.info(
        "[Task %s] Starting agent pipeline for run=%s build=%s type=%s",
        self.request.id, test_run_id, build_number, workflow_type,
    )
    try:
        final_state = _run_async(run_offline_pipeline(
            test_run_id=test_run_id,
            project_id=project_id,
            build_number=build_number,
            workflow_type=workflow_type,
        ))
        stages_done = final_state.get("completed_stages", [])
        errors = final_state.get("errors", [])
        logger.info(
            "[Task %s] Agent pipeline complete. stages=%s errors=%d",
            self.request.id, stages_done, len(errors),
        )
        return {"completed_stages": stages_done, "error_count": len(errors)}
    except Exception as exc:
        logger.error("[Task %s] Agent pipeline failed: %s", self.request.id, exc, exc_info=True)
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
