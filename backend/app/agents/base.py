"""Base agent class shared by all pipeline agents."""
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.metrics import (
    active_pipeline_runs,
    pipeline_stage_duration_seconds,
    pipeline_stage_runs_total,
)
from app.core.tracing import get_tracer
from app.db.postgres import AsyncSessionLocal
from app.models.postgres import AgentStageResult


class BaseAgent(ABC):
    """
    Abstract base for all pipeline agents.
    Provides DB session management, stage result persistence,
    OpenTelemetry span tracking, and Prometheus metrics emission.
    """

    stage_name: str = "unknown"

    def __init__(self):
        self.logger = logging.getLogger(f"agents.{self.stage_name}")
        self._tracer = get_tracer(f"agents.{self.stage_name}")
        # Track per-run start times and OTEL spans so mark_stage_done can calculate duration
        self._stage_start: dict[str, float] = {}
        self._stage_spans: dict[str, Any] = {}

    @abstractmethod
    async def run(self, state: dict) -> dict:
        """Execute the agent logic. Returns partial state update."""

    # ── Stage tracking helpers ─────────────────────────────────────

    async def mark_stage_running(self, pipeline_run_id: str) -> None:
        # Start OTEL span
        span = self._tracer.start_span(
            f"agent.{self.stage_name}",
            attributes={
                "pipeline.run_id": pipeline_run_id,
                "agent.stage": self.stage_name,
            },
        )
        self._stage_spans[pipeline_run_id] = span
        self._stage_start[pipeline_run_id] = time.perf_counter()

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select  # noqa: PLC0415

            result = await db.execute(
                select(AgentStageResult).where(
                    AgentStageResult.pipeline_run_id == pipeline_run_id,
                    AgentStageResult.stage_name == self.stage_name,
                )
            )
            stage = result.scalar_one_or_none()
            if stage:
                stage.status = "running"
                stage.started_at = datetime.now(timezone.utc)
                await db.commit()

    async def mark_stage_done(
        self,
        pipeline_run_id: str,
        result_data: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> None:
        status = "failed" if error else "completed"

        # Record Prometheus stage duration + counter
        duration = time.perf_counter() - self._stage_start.pop(pipeline_run_id, time.perf_counter())
        pipeline_stage_duration_seconds.labels(
            stage_name=self.stage_name, status=status
        ).observe(duration)
        pipeline_stage_runs_total.labels(
            stage_name=self.stage_name, status=status
        ).inc()

        # Close OTEL span
        span = self._stage_spans.pop(pipeline_run_id, None)
        if span is not None:
            try:
                from opentelemetry.trace import StatusCode  # type: ignore  # noqa: PLC0415

                if error:
                    span.set_status(StatusCode.ERROR, error[:200])
                else:
                    span.set_status(StatusCode.OK)
                span.set_attribute("duration_seconds", round(duration, 3))
            except ImportError:
                pass
            finally:
                span.end()

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select  # noqa: PLC0415

            result = await db.execute(
                select(AgentStageResult).where(
                    AgentStageResult.pipeline_run_id == pipeline_run_id,
                    AgentStageResult.stage_name == self.stage_name,
                )
            )
            stage = result.scalar_one_or_none()
            if stage:
                stage.status = status
                stage.completed_at = datetime.now(timezone.utc)
                if result_data:
                    stage.result_data = result_data
                if error:
                    stage.error = error[:2000]
                await db.commit()

    def track_active(self, workflow_type: str, delta: float) -> None:
        """Increment or decrement the active-pipeline-runs Prometheus gauge."""
        active_pipeline_runs.labels(workflow_type=workflow_type).inc(delta)

    async def broadcast_progress(self, project_id: str, payload: dict) -> None:
        """Broadcast pipeline progress event via WebSocket."""
        try:
            from app.routers.live import manager
            await manager.broadcast(
                project_id,
                {"type": "pipeline_progress", "stage": self.stage_name, **payload},
            )
        except Exception as exc:
            self.logger.debug("WebSocket broadcast failed (non-critical): %s", exc)
