"""Base agent class shared by all pipeline agents."""
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from app.db.postgres import AsyncSessionLocal
from app.models.postgres import AgentStageResult


class BaseAgent(ABC):
    """
    Abstract base for all pipeline agents.
    Provides DB session management and stage result persistence.
    """

    stage_name: str = "unknown"

    def __init__(self):
        self.logger = logging.getLogger(f"agents.{self.stage_name}")

    @abstractmethod
    async def run(self, state: dict) -> dict:
        """Execute the agent logic. Returns partial state update."""

    # ── Stage tracking helpers ─────────────────────────────────────

    async def mark_stage_running(self, pipeline_run_id: str) -> None:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
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
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
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
