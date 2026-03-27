"""
Chat / Conversation Agent endpoints.

Provides CRUD for chat sessions and a message endpoint that invokes
the ConversationAgent to answer questions about test results.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.postgres import get_db
from app.models.postgres import ChatMessage, ChatSession, User
from app.models.schemas import (
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    SendMessageRequest,
    SendMessageResponse,
)

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


# ── Pre-computed run summaries ─────────────────────────────────────────────

@router.get("/run-summaries")
async def get_run_summaries(
    project_id: Optional[str] = None,
    days: int = Query(5, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """
    Return pre-computed LLM summaries for test runs from the last N days.

    Strategy:
      1. Fetch AI-generated summaries from MongoDB (instant — no LLM call).
      2. Fetch recent TestRuns from PostgreSQL.
      3. For runs that have no AI summary yet, return a stats-based stub so the
         dashboard always shows something immediately. The stub is replaced by the
         full AI summary once the pipeline completes (~45-60 s after run end).
    """
    from app.db.mongo import Collections, get_mongo_db
    from sqlalchemy import select
    from app.models.postgres import TestRun

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # ── 1. MongoDB AI summaries ────────────────────────────────────────────
    mongo_db = get_mongo_db()
    mongo_query: dict = {"generated_at": {"$gte": cutoff}}
    if project_id:
        mongo_query["project_id"] = project_id

    cursor = mongo_db[Collections.RUN_SUMMARIES].find(
        mongo_query,
        {
            "_id": 0,
            "test_run_id": 1, "project_id": 1, "build_number": 1,
            "executive_summary": 1, "markdown_report": 1,
            "anomaly_count": 1, "is_regression": 1, "analysis_count": 1,
            "generated_at": 1,
        },
    ).sort("generated_at", -1).limit(20)

    ai_summaries = await cursor.to_list(length=20)
    ai_run_ids = {s["test_run_id"] for s in ai_summaries}

    for s in ai_summaries:
        if isinstance(s.get("generated_at"), datetime):
            s["generated_at"] = s["generated_at"].isoformat()
        s["is_stub"] = False

    # ── 2. PostgreSQL TestRun stubs for runs without AI summaries ──────────
    stmt = (
        select(TestRun)
        .where(TestRun.start_time >= cutoff)
        .order_by(TestRun.start_time.desc())
        .limit(20)
    )
    if project_id:
        try:
            stmt = stmt.where(TestRun.project_id == uuid.UUID(project_id))
        except ValueError:
            pass  # invalid UUID — ignore filter, return all

    result = await db.execute(stmt)
    db_runs = result.scalars().all()

    stubs = []
    for run in db_runs:
        if str(run.id) in ai_run_ids:
            continue  # full AI summary already covers this run
        pass_rate = run.pass_rate or 0.0
        total = run.total_tests or 0
        failed = run.failed_tests or 0
        passed = total - failed
        status_word = (
            "completed with no failures"
            if failed == 0
            else f"completed — {failed} test{'s' if failed != 1 else ''} failed"
        )
        exec_summary = (
            f"Build **{run.build_number or str(run.id)[:8]}** {status_word}. "
            f"Pass rate: {pass_rate:.1f}% ({passed}/{total} tests). "
            f"AI analysis is being generated and will appear shortly."
        )
        stubs.append({
            "test_run_id":       str(run.id),
            "project_id":        str(run.project_id),
            "build_number":      run.build_number or "",
            "executive_summary": exec_summary,
            "markdown_report":   None,
            "anomaly_count":     0,
            "is_regression":     False,
            "analysis_count":    0,
            "generated_at":      run.start_time.isoformat() if run.start_time else datetime.now(timezone.utc).isoformat(),
            "is_stub":           True,
        })

    # ── 3. Merge: AI summaries first, then stubs, latest first ─────────────
    combined = ai_summaries + stubs
    combined.sort(key=lambda s: s.get("generated_at", ""), reverse=True)
    return combined[:20]


# ── Sessions ──────────────────────────────────────────────────────

@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all chat sessions for the authenticated user."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
async def create_session(
    payload: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new chat session."""
    session = ChatSession(
        user_id=current_user.id,
        project_id=payload.project_id,
        title=payload.title or "New conversation",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a chat session and all its messages."""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, detail="Session not found")
    await db.delete(session)
    await db.commit()


# ── Messages ──────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_messages(
    session_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get message history for a session."""
    # Verify ownership
    sess_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    if not sess_result.scalar_one_or_none():
        raise HTTPException(404, detail="Session not found")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(
    session_id: uuid.UUID,
    payload: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Send a message to the Conversation Agent and receive an AI reply.
    The agent uses RAG to query test data and returns a markdown response.
    """
    # Verify session belongs to user
    sess_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, detail="Session not found")

    # Auto-update session title from first user message
    if not session.title or session.title == "New conversation":
        session.title = payload.message[:80]
        await db.commit()

    from app.agents.conversation import ConversationAgent
    agent = ConversationAgent()
    result = await agent.chat(
        session_id=str(session_id),
        user_message=payload.message,
        user_id=str(current_user.id),
        project_id=str(session.project_id) if session.project_id else payload.project_id,
    )

    return SendMessageResponse(
        session_id=session_id,
        reply=result["reply"],
        sources=result["sources"],
    )
