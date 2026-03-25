"""
Live test reporting via WebSocket.
Clients subscribe to a project channel and receive real-time updates
when new test runs are ingested or test case statuses change.
"""
import asyncio
import json
import logging
from typing import Set

from fastapi import APIRouter, Body, Depends, HTTPException, WebSocket, WebSocketDisconnect
from app.core.deps import verify_webhook_secret

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["Live Reporting"])

# ── Connection manager ─────────────────────────────────────────────────────

class ConnectionManager:
    """Manages WebSocket connections per project channel."""

    def __init__(self):
        # project_id -> set of WebSocket connections
        self._channels: dict[str, Set[WebSocket]] = {}

    async def connect(self, project_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if project_id not in self._channels:
            self._channels[project_id] = set()
        self._channels[project_id].add(websocket)
        logger.info(f"WS connect: project={project_id} total={len(self._channels[project_id])}")

    def disconnect(self, project_id: str, websocket: WebSocket) -> None:
        channel = self._channels.get(project_id, set())
        channel.discard(websocket)
        if not channel:
            self._channels.pop(project_id, None)
        logger.info(f"WS disconnect: project={project_id}")

    async def broadcast(self, project_id: str, message: dict) -> None:
        """Send a message to all connected clients in a project channel."""
        channel = self._channels.get(project_id, set())
        if not channel:
            return
        dead: Set[WebSocket] = set()
        payload = json.dumps(message)
        for ws in list(channel):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(project_id, ws)

    async def broadcast_all(self, message: dict) -> None:
        """Broadcast to all connected clients across all projects."""
        for project_id in list(self._channels.keys()):
            await self.broadcast(project_id, message)

    @property
    def active_connections(self) -> int:
        return sum(len(v) for v in self._channels.values())


manager = ConnectionManager()


# ── WebSocket endpoint ─────────────────────────────────────────────────────

@router.websocket("/live/{project_id}")
async def live_updates(websocket: WebSocket, project_id: str):
    """
    WebSocket endpoint for real-time test run updates.

    Message types sent to client:
    - run_started: A new test run has been queued for ingestion
    - run_updated: Test run aggregates (pass/fail counts) have changed
    - run_completed: Ingestion finished, final stats available
    - test_failed: Individual test case failed
    - ai_analysis_ready: AI analysis completed for a test case
    - ping: Keep-alive heartbeat every 30s

    Message types received from client:
    - ping: Client keep-alive (server responds with pong)
    """
    await manager.connect(project_id, websocket)
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "project_id": project_id,
            "message": "Subscribed to live test updates",
        })

        # Keep connection alive with ping/pong
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Send server-side heartbeat
                await websocket.send_json({"type": "ping"})
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(project_id, websocket)
    except Exception as e:
        logger.warning(f"WS error for project={project_id}: {e}")
        manager.disconnect(project_id, websocket)


# ── Helper functions called from ingestion pipeline ───────────────────────

async def notify_run_started(project_id: str, run_id: str, build_number: str) -> None:
    await manager.broadcast(project_id, {
        "type": "run_started",
        "run_id": run_id,
        "build_number": build_number,
    })


async def notify_run_completed(project_id: str, run_id: str, stats: dict) -> None:
    await manager.broadcast(project_id, {
        "type": "run_completed",
        "run_id": run_id,
        **stats,
    })


async def notify_test_failed(project_id: str, run_id: str, test_id: str, test_name: str) -> None:
    await manager.broadcast(project_id, {
        "type": "test_failed",
        "run_id": run_id,
        "test_id": test_id,
        "test_name": test_name,
    })


async def notify_ai_ready(project_id: str, test_id: str, confidence: int, category: str) -> None:
    await manager.broadcast(project_id, {
        "type": "ai_analysis_ready",
        "test_id": test_id,
        "confidence_score": confidence,
        "failure_category": category,
    })


# ── Live execution event ingestion (HTTP) ──────────────────────────────────
# Called by test runners (e.g. pytest plugin, Allure listener) during execution


@router.post("/events/{run_id}", dependencies=[Depends(verify_webhook_secret)], status_code=202)
async def ingest_live_event(
    run_id: str,
    event: dict = Body(...),
):
    """
    Receive a live test execution event from a test runner.
    Supported event types:
      - run_start: {type, project_id, build_number, total_tests}
      - test_result: {type, test_name, status, duration_ms, error_message}
      - run_complete: {type}

    Protected by X-Webhook-Secret header.
    """
    from app.agents.live_monitor import LiveMonitorAgent
    from app.db.mongo import Collections, get_mongo_db

    event_type = event.get("type", "test_result")

    # Persist raw event to MongoDB for audit
    try:
        db = get_mongo_db()
        await db[Collections.LIVE_EXECUTION_EVENTS].insert_one(
            {"run_id": run_id, **event}
        )
    except Exception:
        pass  # Non-critical

    if event_type == "run_start":
        project_id = event.get("project_id")
        build_number = event.get("build_number", run_id)
        if not project_id:
            raise HTTPException(400, detail="project_id required for run_start event")
        await LiveMonitorAgent.on_run_start(run_id, project_id, build_number)

    elif event_type == "test_result":
        await LiveMonitorAgent.on_test_event(run_id, event)

    elif event_type == "run_complete":
        await LiveMonitorAgent.on_run_complete(run_id)

    return {"accepted": True}
