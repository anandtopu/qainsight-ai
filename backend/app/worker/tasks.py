"""Celery background tasks for ingestion and AI analysis."""
import asyncio
import logging
import random

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


def _exponential_backoff(attempt: int, base: int = 30, cap: int = 600) -> int:
    """Return jittered exponential backoff seconds: min(base * 2^attempt, cap) ± 20%."""
    delay = min(base * (2 ** attempt), cap)
    jitter = delay * 0.2 * random.random()
    return int(delay + jitter)


# ── Deduplication helper ──────────────────────────────────────────────────────

async def _is_duplicate(key: str, ttl: int = 3600) -> bool:
    """
    Return True if `key` already exists in Redis (task already running/done).
    Otherwise, set the key with TTL and return False.
    """
    from app.db.redis_client import get_redis
    redis = get_redis()
    # SET NX — only sets if key does not exist; returns True on first write
    was_set = await redis.set(key, "1", ex=ttl, nx=True)
    return not bool(was_set)


# ── Tasks ─────────────────────────────────────────────────────────────────────

@celery_app.task(
    name="app.worker.tasks.ingest_test_run",
    bind=True,
    max_retries=3,
    queue="ingestion",
)
def ingest_test_run(self, sentinel_dict: dict, minio_prefix: str):
    """
    Background task: parse Allure JSON + TestNG XML from MinIO and
    upsert structured data into PostgreSQL + MongoDB.
    Deduplicates by minio_prefix so concurrent webhooks don't double-ingest.
    """
    from app.models.schemas import SentinelFile
    from app.services.ingestion import process_sentinel

    dedup_key = f"qainsight:dedup:ingest:{minio_prefix}"

    async def _run():
        if await _is_duplicate(dedup_key):
            logger.info("[Task %s] Skipping duplicate ingestion for %s", self.request.id, minio_prefix)
            return
        sentinel = SentinelFile(**sentinel_dict)
        await process_sentinel(sentinel, minio_prefix)

    logger.info("[Task %s] Starting ingestion: %s", self.request.id, minio_prefix)
    try:
        _run_async(_run())
        logger.info("[Task %s] Ingestion complete", self.request.id)
    except Exception as exc:
        logger.error("[Task %s] Ingestion failed: %s", self.request.id, exc, exc_info=True)
        countdown = _exponential_backoff(self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(
    name="app.worker.tasks.run_live_test_analysis",
    bind=True,
    max_retries=2,
    queue="critical",
    time_limit=120,
    priority=9,
)
def run_live_test_analysis(
    self,
    test_case_id: str,
    test_name: str,
    run_id: str,
    project_id: str,
):
    """
    Immediate root-cause analysis for a single test that failed during live execution.
    Runs on the critical queue (priority=9) so results appear in the dashboard fast.
    Protected by the LLM circuit breaker — skips silently if the provider is down.
    """
    from app.services.agent import run_triage_agent
    from app.streams.circuit_breaker import LLMCircuitBreaker

    async def _run():
        if not await LLMCircuitBreaker.is_available():
            retry_after = await LLMCircuitBreaker.retry_after_seconds()
            logger.info(
                "[Task %s] Circuit open — skipping live analysis for %s (retry in %ds)",
                self.request.id, test_name, retry_after,
            )
            return None

        try:
            result = await run_triage_agent(
                test_case_id=test_case_id,
                test_name=test_name,
                run_id=run_id,
                project_id=project_id,
            )
            await LLMCircuitBreaker.record_success()
            return result
        except Exception:
            await LLMCircuitBreaker.record_failure()
            raise

    logger.info("[Task %s] Live analysis for test=%s run=%s", self.request.id, test_name, run_id)
    try:
        result = _run_async(_run())
        if result:
            logger.info(
                "[Task %s] Live analysis complete. confidence=%s",
                self.request.id, result.get("confidence_score"),
            )
        return result
    except Exception as exc:
        logger.error("[Task %s] Live analysis failed: %s", self.request.id, exc, exc_info=True)
        countdown = _exponential_backoff(self.request.retries, base=10, cap=60)
        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(
    name="app.worker.tasks.run_ai_analysis",
    bind=True,
    max_retries=2,
    queue="ai_analysis",
    time_limit=180,
)
def run_ai_analysis(self, test_case_id: str, test_name: str, **kwargs):
    """
    Background task: run the LangChain ReAct agent for a single test case.
    Used by the offline auto-analyzer. Protected by the LLM circuit breaker.
    """
    from app.services.agent import run_triage_agent
    from app.streams.circuit_breaker import LLMCircuitBreaker

    async def _run():
        if not await LLMCircuitBreaker.is_available():
            retry_after = await LLMCircuitBreaker.retry_after_seconds()
            raise RuntimeError(f"LLM circuit open — retry in {retry_after}s")

        try:
            result = await run_triage_agent(
                test_case_id=test_case_id,
                test_name=test_name,
                **kwargs,
            )
            await LLMCircuitBreaker.record_success()
            return result
        except Exception:
            await LLMCircuitBreaker.record_failure()
            raise

    logger.info("[Task %s] AI analysis for: %s", self.request.id, test_name)
    try:
        result = _run_async(_run())
        logger.info("[Task %s] Analysis complete. confidence=%s", self.request.id, result.get("confidence_score"))
        return result
    except Exception as exc:
        logger.error("[Task %s] AI analysis failed: %s", self.request.id, exc, exc_info=True)
        countdown = _exponential_backoff(self.request.retries, base=60, cap=300)
        raise self.retry(exc=exc, countdown=countdown)


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
    max_retries=2,
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
    Background task: run the full multi-agent LangGraph pipeline for a completed test run.
    Stages: ingestion → anomaly detection → root-cause analysis → summary → triage
    Deduplicates by test_run_id so multiple triggers for the same run don't stack up.
    Moves to DLQ after max retries.
    """
    from app.agents.workflow import run_offline_pipeline

    dedup_key = f"qainsight:dedup:pipeline:{test_run_id}"

    async def _run():
        if await _is_duplicate(dedup_key, ttl=7200):
            logger.info(
                "[Task %s] Skipping duplicate pipeline for run=%s",
                self.request.id, test_run_id,
            )
            return {"completed_stages": [], "error_count": 0, "duplicate": True}
        return await run_offline_pipeline(
            test_run_id=test_run_id,
            project_id=project_id,
            build_number=build_number,
            workflow_type=workflow_type,
        )

    logger.info(
        "[Task %s] Starting agent pipeline run=%s build=%s type=%s",
        self.request.id, test_run_id, build_number, workflow_type,
    )
    try:
        final_state = _run_async(_run())
        stages_done = final_state.get("completed_stages", [])
        errors = final_state.get("errors", [])
        logger.info(
            "[Task %s] Pipeline complete. stages=%s errors=%d",
            self.request.id, stages_done, len(errors),
        )
        return {"completed_stages": stages_done, "error_count": len(errors)}
    except Exception as exc:
        logger.error("[Task %s] Pipeline failed: %s", self.request.id, exc, exc_info=True)
        if self.request.retries >= self.max_retries:
            # Move to DLQ before the final exception propagates
            _run_async(_send_to_dlq(
                task_name=self.name,
                task_id=self.request.id,
                kwargs={"test_run_id": test_run_id, "build_number": build_number},
                error=str(exc),
            ))
        countdown = _exponential_backoff(self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


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
            logger.info("Taking coverage snapshot for %d projects", len(projects))
            for project in projects:
                logger.info("  Snapshot: %s", project.name)

    logger.info("Running daily coverage snapshot task")
    _run_async(_run())


# ── DLQ helper ────────────────────────────────────────────────────────────────

async def _send_to_dlq(task_name: str, task_id: str, kwargs: dict, error: str) -> None:
    """Write a failed task to the Redis DLQ stream for manual inspection and replay."""
    try:
        import json
        from app.db.redis_client import get_redis
        from app.streams import DLQ_STREAM
        redis = get_redis()
        await redis.xadd(
            DLQ_STREAM,
            {
                "source": "celery",
                "task_name": task_name,
                "task_id": task_id,
                "kwargs": json.dumps(kwargs),
                "error": error[:500],
            },
            maxlen=5000,
            approximate=True,
        )
        logger.error("Moved failed task to DLQ: task=%s id=%s error=%s", task_name, task_id, error)
    except Exception as dlq_exc:
        logger.error("Failed to write to DLQ: %s", dlq_exc)
