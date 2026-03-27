"""
Live Test Execution Streaming API

Endpoints used by client machines to stream test execution results to QA Insight AI
in real-time. Designed to handle 10 000+ concurrent test executions with eventual
consistency guarantees for the stored results.

Flow
----
1. Client registers a session (JWT-authenticated, one-time):
       POST /api/v1/stream/sessions
   Returns a short-lived session_token for lightweight auth on subsequent calls.

2. During execution, client sends batched events (hot path — no JWT overhead):
       POST /api/v1/stream/events/batch
       Header: X-Session-Token: <token>
   Each call carries up to 1 000 events. Server returns 202 immediately.
   All events are enqueued to Redis Streams via pipeline (one round-trip).

3. Dashboard viewers subscribe to real-time updates:
       WebSocket : /ws/live/{project_id}   (existing)
       SSE       : GET /api/v1/stream/sse/{project_id}?token=<jwt>  (new)

4. When execution finishes, client completes the session:
       DELETE /api/v1/stream/sessions/{session_id}
   This marks the run as complete and triggers the offline AI pipeline.

Scale notes
-----------
- Token auth is a single Redis GET (O(1)) — no DB round-trip on the hot path.
- Batch publishing uses a Redis pipeline — all XADDs in one TCP round-trip.
- Redis Streams consumer group handles fan-out to WebSocket clients.
- PostgreSQL rows are written after run completion (eventual consistency).
"""

import asyncio
import hashlib
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.postgres import get_db
from app.db.redis_client import get_redis
from app.models.postgres import LaunchStatus, LiveSession, Project, TestRun
from app.models.schemas import (
    ActiveSessionsResponse,
    LiveEventBatch,
    LiveEventBatchResponse,
    LiveSessionCreate,
    LiveSessionResponse,
    LiveSessionState,
)
from app.streams import SESSION_TOKEN_KEY
from app.streams.producer import publish_event_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stream", tags=["Live Stream"])

# ── SSE subscriber registry ────────────────────────────────────────────────
# project_id → set of asyncio.Queue instances (one per connected SSE client)
_sse_subscribers: dict[str, set[asyncio.Queue]] = {}

_SESSION_TTL = 86_400   # 24 hours


# ── Session lifecycle ──────────────────────────────────────────────────────

@router.post("/sessions", response_model=LiveSessionResponse, status_code=201)
async def create_session(
    payload: LiveSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Register a new live execution session.

    Returns a session_token that the client uses on every subsequent
    POST /events/batch call (via X-Session-Token header).
    Token validation is O(1) Redis GET — no JWT overhead in the hot path.
    """
    project = await db.get(Project, payload.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    session_id = str(uuid.uuid4())
    run_id = payload.run_id or session_id
    session_token = secrets.token_urlsafe(32)

    session = LiveSession(
        id=uuid.UUID(session_id),
        project_id=payload.project_id,
        run_id=run_id,
        client_name=payload.client_name,
        machine_id=payload.machine_id,
        build_number=payload.build_number,
        framework=payload.framework,
        branch=payload.branch,
        commit_hash=payload.commit_hash,
        session_token_hash=_hash_token(session_token),
        total_tests=payload.total_tests or 0,
        status="active",
        release_name=payload.release_name or None,
        started_at=datetime.now(timezone.utc),
        extra_metadata=payload.metadata or {},
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # Store plaintext token → session_id in Redis for fast hot-path auth
    redis = get_redis()
    await redis.setex(
        SESSION_TOKEN_KEY.format(token=session_token),
        _SESSION_TTL,
        session_id,
    )

    # Initialise live aggregates in Redis (atomic counters for the consumer)
    from app.streams.live_run_state import RedisLiveRunState
    await RedisLiveRunState.start(
        run_id=run_id,
        project_id=str(payload.project_id),
        build_number=payload.build_number or session_id,
        total_tests=payload.total_tests or 0,
    )

    logger.info(
        "Live session created: session=%s run=%s project=%s framework=%s",
        session_id, run_id, payload.project_id, payload.framework,
    )
    return LiveSessionResponse(
        session_id=session_id,
        session_token=session_token,
        run_id=run_id,
        project_id=str(payload.project_id),
        expires_in=_SESSION_TTL,
        created_at=session.started_at,
    )


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """Return session metadata + live aggregated stats from Redis."""
    try:
        uid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid session_id format")

    session = await db.get(LiveSession, uid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    from app.streams.live_run_state import RedisLiveRunState
    live_stats = await RedisLiveRunState.get(session.run_id) or {}

    return {
        "session_id": str(session.id),
        "run_id": session.run_id,
        "project_id": str(session.project_id),
        "client_name": session.client_name,
        "machine_id": session.machine_id,
        "build_number": session.build_number,
        "framework": session.framework,
        "branch": session.branch,
        "status": session.status,
        "total_tests": session.total_tests,
        "events_received": session.events_received,
        "started_at": session.started_at.isoformat(),
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "live_stats": live_stats,
    }


@router.delete("/sessions/{session_id}", status_code=204)
async def close_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """
    Mark session as complete, finalise Redis state, and trigger the offline
    AI analysis pipeline for full persistence to PostgreSQL.
    """
    try:
        uid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid session_id format")

    session = await db.get(LiveSession, uid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Finalise Redis aggregates first so we can snapshot them into DB
    from app.streams.live_run_state import RedisLiveRunState
    state = await RedisLiveRunState.complete(session.run_id)

    now = datetime.now(timezone.utc)
    session.status = "completed"
    session.completed_at = now
    # Persist final aggregates so list_active_sessions can return completed data
    if state:
        session.extra_metadata = {**(session.extra_metadata or {}), "final_state": state}

    # Create (or update) a TestRun row immediately — no Celery dependency.
    # This guarantees data survives Redis/Celery restarts.
    await _upsert_test_run(db, session, state or {})

    # Link to release if a release_name was provided at session creation.
    if session.release_name and session.release_name.strip():
        try:
            from app.services.release_linker import auto_link_release
            import uuid as _uuid
            _run_uuid = _uuid.UUID(session.run_id)
            await auto_link_release(
                db=db,
                project_id=session.project_id,
                release_name=session.release_name.strip(),
                test_run_id=_run_uuid,
            )
        except Exception as _rel_err:
            logger.warning(
                "Release linking failed for live session %s: %s", session_id, _rel_err
            )

    await db.commit()

    # Persist TestRun + TestCase rows to PostgreSQL from the Redis event buffer
    try:
        from app.worker.tasks import persist_live_session
        persist_live_session.apply_async(
            kwargs={
                "run_id":       session.run_id,
                "project_id":   str(session.project_id),
                "build_number": session.build_number or session_id,
                "client_name":  session.client_name,
                "framework":    session.framework or "",
                "branch":       session.branch or "",
                "commit_hash":  session.commit_hash or "",
                "final_state":  state or {},
            },
            queue="ingestion",
            priority=7,
        )
        logger.info("Queued persist_live_session for session %s", session_id)
    except Exception as exc:
        logger.warning(
            "Failed to queue persist_live_session for session %s: %s", session_id, exc
        )

    # Trigger the full AI analysis pipeline (anomaly detection → root-cause → summary → triage).
    # countdown=45s lets persist_live_session write TestRun/TestCase rows first.
    try:
        from app.worker.tasks import run_agent_pipeline
        run_agent_pipeline.apply_async(
            kwargs={
                "test_run_id":   session.run_id,
                "project_id":    str(session.project_id),
                "build_number":  session.build_number or session_id,
                "workflow_type": "live",
            },
            queue="ai_analysis",
            priority=6,
            countdown=45,
        )
        logger.info("Queued AI pipeline for session %s (run %s)", session_id, session.run_id)
    except Exception as exc:
        logger.warning(
            "Failed to queue AI pipeline for session %s: %s", session_id, exc
        )

    return None


# ── Batch event ingestion (hot path) ──────────────────────────────────────

@router.post("/events/batch", response_model=LiveEventBatchResponse, status_code=202)
async def ingest_event_batch(
    batch: LiveEventBatch,
    x_session_token: str = Header(..., alias="X-Session-Token"),
):
    """
    Accept a batch of test execution events from a client machine.

    This is the high-throughput hot path:
    - Auth: single Redis GET (O(1)) — no JWT decode, no DB query
    - Publish: Redis pipeline — all XADDs in one TCP round-trip
    - Response: 202 immediately — processing is fully async

    Supports up to 1 000 events per call.
    Typical usage: client flushes every 100 ms or every 50 events.
    At 10k concurrent sessions × 50 events per flush = 500 000 events/s peak,
    handled by Redis Streams with consumer group fan-out.
    """
    # Fast O(1) token validation
    redis = get_redis()
    stored_session_id = await redis.get(
        SESSION_TOKEN_KEY.format(token=x_session_token)
    )
    if not stored_session_id or stored_session_id != batch.session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        )

    # Publish entire batch to Redis Streams (single pipeline round-trip)
    accepted = await publish_event_batch(
        session_id=batch.session_id,
        run_id=batch.run_id,
        events=batch.events,
    )

    # Refresh session TTL while activity continues
    await redis.expire(
        SESSION_TOKEN_KEY.format(token=x_session_token), _SESSION_TTL
    )

    return LiveEventBatchResponse(
        accepted=accepted,
        run_id=batch.run_id,
        session_id=batch.session_id,
    )


# ── Active sessions dashboard ─────────────────────────────────────────────

@router.get("/active", response_model=ActiveSessionsResponse)
async def list_active_sessions(
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """
    Return active live sessions (Redis) plus sessions completed in the last 7 days (DB).
    Used by the live execution dashboard.
    Optional project_id query param to filter by project.
    """
    from app.streams.live_run_state import RedisLiveRunState
    from sqlalchemy import select

    # ── Redis active sessions ──────────────────────────────────────────────
    all_active = await RedisLiveRunState.get_all_active()
    if project_id:
        all_active = [s for s in all_active if s.get("project_id") == project_id]

    active_run_ids = {s.get("run_id") for s in all_active}

    active_sessions = [
        LiveSessionState(
            run_id=s.get("run_id", ""),
            project_id=s.get("project_id", ""),
            build_number=s.get("build_number", ""),
            status=s.get("status", "running"),
            total=int(s.get("total", 0)),
            passed=int(s.get("passed", 0)),
            failed=int(s.get("failed", 0)),
            skipped=int(s.get("skipped", 0)),
            broken=int(s.get("broken", 0)),
            pass_rate=float(s.get("pass_rate", 0.0)),
            current_test=s.get("current_test") or None,
            started_at=s.get("started_at"),
            last_event_at=s.get("last_event_at"),
        )
        for s in all_active
    ]

    # ── Recently completed sessions from live_sessions table (last 7 days) ─
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    stmt = select(LiveSession).where(
        LiveSession.status == "completed",
        LiveSession.completed_at >= cutoff,
    ).order_by(LiveSession.completed_at.desc()).limit(50)
    if project_id:
        try:
            stmt = stmt.where(LiveSession.project_id == uuid.UUID(project_id))
        except ValueError:
            pass

    result = await db.execute(stmt)
    db_sessions = result.scalars().all()

    # Track which run_ids we've already included to avoid duplicates
    seen_run_ids = set(active_run_ids)

    completed_sessions = []
    for s in db_sessions:
        if s.run_id in seen_run_ids:
            continue
        seen_run_ids.add(s.run_id)
        fs = (s.extra_metadata or {}).get("final_state", {})
        completed_sessions.append(
            LiveSessionState(
                run_id=s.run_id,
                project_id=str(s.project_id),
                build_number=s.build_number or "",
                status="completed",
                total=int(fs.get("total", s.total_tests or 0)),
                passed=int(fs.get("passed", 0)),
                failed=int(fs.get("failed", 0)),
                skipped=int(fs.get("skipped", 0)),
                broken=int(fs.get("broken", 0)),
                pass_rate=float(fs.get("pass_rate", 0.0)),
                current_test=None,
                started_at=s.started_at.isoformat() if s.started_at else None,
                last_event_at=s.completed_at.isoformat() if s.completed_at else None,
                client_name=s.client_name,
                completed_at=s.completed_at.isoformat() if s.completed_at else None,
                release_name=s.release_name or None,
            )
        )

    # ── TestRun fallback (last 7 days, trigger_source=live_stream) ─────────
    # Catches runs that persisted to TestRun but whose LiveSession row is
    # missing or outside the live_sessions query (e.g. after a DB migration).
    tr_stmt = (
        select(TestRun)
        .where(
            TestRun.trigger_source == "live_stream",
            TestRun.start_time >= cutoff,
        )
        .order_by(TestRun.start_time.desc())
        .limit(50)
    )
    if project_id:
        try:
            tr_stmt = tr_stmt.where(TestRun.project_id == uuid.UUID(project_id))
        except ValueError:
            pass

    tr_result = await db.execute(tr_stmt)
    tr_runs = tr_result.scalars().all()

    for run in tr_runs:
        if str(run.id) in seen_run_ids:
            continue
        seen_run_ids.add(str(run.id))
        passed  = run.passed_tests or 0
        failed  = run.failed_tests or 0
        skipped = run.skipped_tests or 0
        broken  = run.broken_tests or 0
        total   = run.total_tests or 0
        completed_sessions.append(
            LiveSessionState(
                run_id=str(run.id),
                project_id=str(run.project_id),
                build_number=run.build_number or "",
                status="completed",
                total=total,
                passed=passed,
                failed=failed,
                skipped=skipped,
                broken=broken,
                pass_rate=float(run.pass_rate or 0.0),
                current_test=None,
                started_at=run.start_time.isoformat() if run.start_time else None,
                last_event_at=run.end_time.isoformat() if run.end_time else None,
                client_name=None,
                completed_at=run.end_time.isoformat() if run.end_time else None,
            )
        )

    all_sessions = active_sessions + completed_sessions
    return ActiveSessionsResponse(sessions=all_sessions, count=len(all_sessions))


# ── SSE dashboard stream ───────────────────────────────────────────────────

@router.get("/sse/{project_id}")
async def sse_stream(
    project_id: str,
    request: Request,
    token: str,
):
    """
    Server-Sent Events stream for the live execution dashboard.

    Use this when WebSocket is unavailable (HTTP/2 proxies, some CI environments).
    The browser EventSource API cannot send custom headers, so the JWT is passed
    as a query parameter instead.

    Connect:
        const es = new EventSource(
            `/api/v1/stream/sse/${projectId}?token=${jwt}`
        );

    Message types pushed to clients mirror the WebSocket protocol:
        live_run_started | live_test_result | live_warning | live_run_complete
    """
    from app.core.security import decode_token
    from jose import JWTError  # type: ignore

    try:
        decode_token(token)
    except (JWTError, Exception):
        raise HTTPException(status_code=401, detail="Invalid token")

    queue: asyncio.Queue = asyncio.Queue(maxsize=500)

    if project_id not in _sse_subscribers:
        _sse_subscribers[project_id] = set()
    _sse_subscribers[project_id].add(queue)

    async def generate() -> AsyncGenerator[str, None]:
        try:
            # Send initial state snapshot so the client doesn't start from blank
            from app.streams.live_run_state import RedisLiveRunState
            active = await RedisLiveRunState.get_all_active()
            project_sessions = [s for s in active if s.get("project_id") == project_id]
            yield (
                "data: "
                + json.dumps({"type": "initial_state", "sessions": project_sessions})
                + "\n\n"
            )

            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield "data: " + json.dumps(msg) + "\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat comment — keeps proxies from killing idle connections
                    yield ": heartbeat\n\n"
        finally:
            _sse_subscribers.get(project_id, set()).discard(queue)
            if project_id in _sse_subscribers and not _sse_subscribers[project_id]:
                del _sse_subscribers[project_id]

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",    # disable nginx buffering
            "Connection": "keep-alive",
        },
    )


# ── Internal helper: push to SSE subscribers ──────────────────────────────
# Called by the live_consumer background task to fan-out events to SSE clients

async def push_to_sse(project_id: str, message: dict) -> None:
    """Push a message to all SSE subscribers watching this project."""
    subscribers = _sse_subscribers.get(project_id, set())
    if not subscribers:
        return
    dead: set[asyncio.Queue] = set()
    for queue in list(subscribers):
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            dead.add(queue)
    for q in dead:
        subscribers.discard(q)


# ── Private helpers ────────────────────────────────────────────────────────

def _hash_token(token: str) -> str:
    """SHA-256 hash of a plaintext session token — stored in PostgreSQL."""
    return hashlib.sha256(token.encode()).hexdigest()


async def _upsert_test_run(db: AsyncSession, session: LiveSession, state: dict) -> None:
    """
    Create or update a TestRun row from a closing live session.

    Called synchronously inside close_session — guarantees the TestRun row
    exists in PostgreSQL regardless of whether the Celery worker is running.
    The Celery persist_live_session task will later fill in individual TestCase
    rows and update aggregates from the Redis event buffer (if still available).
    """
    from sqlalchemy import select

    # Resolve run_id to a deterministic UUID
    try:
        run_uuid = uuid.UUID(session.run_id)
    except ValueError:
        run_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, session.run_id)

    passed  = int(state.get("passed",  0))
    failed  = int(state.get("failed",  0))
    skipped = int(state.get("skipped", 0))
    broken  = int(state.get("broken",  0))
    total   = int(state.get("total",   session.total_tests or 0))
    pass_rate = (
        round(passed / (passed + failed + broken) * 100, 2)
        if (passed + failed + broken) > 0
        else None
    )
    run_status = LaunchStatus.FAILED if (failed + broken) > 0 else LaunchStatus.PASSED
    now = datetime.now(timezone.utc)

    existing = await db.execute(select(TestRun).where(TestRun.id == run_uuid))
    run = existing.scalar_one_or_none()

    if run is None:
        run = TestRun(
            id=run_uuid,
            project_id=session.project_id,
            build_number=session.build_number or str(session.id)[:8],
            trigger_source="live_stream",
            branch=session.branch or None,
            commit_hash=session.commit_hash or None,
            status=run_status,
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            skipped_tests=skipped,
            broken_tests=broken,
            pass_rate=pass_rate,
            start_time=session.started_at or now,
            end_time=now,
        )
        db.add(run)
        logger.info("Created TestRun %s for live session %s", run_uuid, session.id)
    else:
        run.status        = run_status
        run.total_tests   = total
        run.passed_tests  = passed
        run.failed_tests  = failed
        run.skipped_tests = skipped
        run.broken_tests  = broken
        run.pass_rate     = pass_rate
        run.end_time      = now
        logger.info("Updated TestRun %s for live session %s", run_uuid, session.id)
