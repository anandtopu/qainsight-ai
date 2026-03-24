"""
Live Test Execution Monitor Agent.

Tracks real-time test execution events sent via the /api/v1/live/events endpoint.
Maintains per-run in-memory state and broadcasts incremental updates over WebSocket.
When a run completion event is received, it triggers the offline pipeline.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from app.db.postgres import AsyncSessionLocal
from app.models.postgres import LaunchStatus, TestRun

logger = logging.getLogger("agents.live_monitor")

# In-memory registry: run_id -> LiveRunState
_active_runs: dict[str, "LiveRunState"] = {}
_lock = asyncio.Lock()


class LiveRunState:
    """Mutable state for a single in-progress test run."""

    def __init__(self, run_id: str, project_id: str, build_number: str):
        self.run_id = run_id
        self.project_id = project_id
        self.build_number = build_number
        self.started_at = datetime.now(timezone.utc)
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.broken = 0
        self.current_test: Optional[str] = None
        self.last_event_at = datetime.now(timezone.utc)

    @property
    def pass_rate(self) -> float:
        completed = self.passed + self.failed + self.broken
        return round((self.passed / completed * 100), 2) if completed else 0.0

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "build_number": self.build_number,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "broken": self.broken,
            "pass_rate": self.pass_rate,
            "current_test": self.current_test,
            "started_at": self.started_at.isoformat(),
            "last_event_at": self.last_event_at.isoformat(),
        }


class LiveMonitorAgent:
    """
    Stateful agent that manages live test execution monitoring.

    Usage:
        # When a run starts (called from live router)
        await LiveMonitorAgent.on_run_start(run_id, project_id, build_number)

        # For each test event
        await LiveMonitorAgent.on_test_event(run_id, event)

        # When complete
        await LiveMonitorAgent.on_run_complete(run_id)
    """

    @staticmethod
    async def on_run_start(run_id: str, project_id: str, build_number: str) -> None:
        """Register a new live run."""
        async with _lock:
            _active_runs[run_id] = LiveRunState(run_id, project_id, build_number)
        logger.info("Live monitor started for run %s (build=%s)", run_id, build_number)

        await _broadcast(project_id, {
            "type": "live_run_started",
            "run_id": run_id,
            "build_number": build_number,
        })

    @staticmethod
    async def on_test_event(run_id: str, event: dict) -> None:
        """Process a single test result event and broadcast the update."""
        async with _lock:
            state = _active_runs.get(run_id)
            if not state:
                return

        status = (event.get("status") or "").upper()
        state.last_event_at = datetime.now(timezone.utc)
        state.total = max(state.total, event.get("total_tests", state.total))
        state.current_test = event.get("test_name")

        if status == "PASSED":
            state.passed += 1
        elif status == "FAILED":
            state.failed += 1
        elif status == "SKIPPED":
            state.skipped += 1
        elif status == "BROKEN":
            state.broken += 1

        await _broadcast(state.project_id, {
            "type": "live_test_result",
            **state.to_dict(),
            "last_test": event.get("test_name"),
            "last_status": status,
        })

        # Early warning: failure rate > 50% after at least 10 tests
        completed = state.passed + state.failed + state.broken
        if completed >= 10 and state.pass_rate < 50:
            await _broadcast(state.project_id, {
                "type": "live_warning",
                "run_id": run_id,
                "message": f"High failure rate: {100 - state.pass_rate:.0f}% of tests failing",
            })

    @staticmethod
    async def on_run_complete(run_id: str) -> None:
        """Finalise a live run and trigger the offline analysis pipeline."""
        async with _lock:
            state = _active_runs.pop(run_id, None)
        if not state:
            return

        logger.info(
            "Live run %s complete. pass_rate=%.1f%%  total=%d",
            run_id, state.pass_rate, state.total,
        )

        # Update DB run status
        await _finalise_run_in_db(run_id, state)

        await _broadcast(state.project_id, {
            "type": "live_run_complete",
            "run_id": run_id,
            **state.to_dict(),
        })

        # Trigger the offline analysis pipeline
        try:
            from app.worker.tasks import run_agent_pipeline
            run_agent_pipeline.delay(
                test_run_id=run_id,
                project_id=state.project_id,
                build_number=state.build_number,
                workflow_type="live",
            )
        except Exception as exc:
            logger.error("Failed to trigger offline pipeline after live run: %s", exc)

    @staticmethod
    def get_active_runs() -> list[dict]:
        return [s.to_dict() for s in _active_runs.values()]

    @staticmethod
    def get_run_state(run_id: str) -> Optional[dict]:
        state = _active_runs.get(run_id)
        return state.to_dict() if state else None


async def _broadcast(project_id: str, payload: dict) -> None:
    try:
        from app.routers.live import manager
        await manager.broadcast(project_id, payload)
    except Exception as exc:
        logger.debug("WebSocket broadcast skipped: %s", exc)


async def _finalise_run_in_db(run_id: str, state: LiveRunState) -> None:
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(select(TestRun).where(TestRun.id == run_id))
            run = result.scalar_one_or_none()
            if run and run.status == LaunchStatus.IN_PROGRESS:
                run.status = LaunchStatus.FAILED if state.failed > 0 else LaunchStatus.PASSED
                run.end_time = datetime.now(timezone.utc)
                await db.commit()
    except Exception as exc:
        logger.error("Failed to finalise run %s in DB: %s", run_id, exc)
