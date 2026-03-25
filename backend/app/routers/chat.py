"""
Chat / Conversation Agent endpoints.

Provides CRUD for chat sessions and a message endpoint that invokes
the ConversationAgent to answer questions about test results.
"""
import uuid

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
