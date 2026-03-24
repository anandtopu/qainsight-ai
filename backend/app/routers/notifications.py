"""Notification preference management and history endpoints."""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.postgres import get_db
from app.models.postgres import (
    NotificationLog,
    NotificationPreference,
    User,
)
from app.models.schemas import (
    NotificationLogResponse,
    NotificationPreferenceCreate,
    NotificationPreferenceResponse,
    TestNotificationRequest,
)
from app.services.notification.manager import send_test_notification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


# ── Preferences ───────────────────────────────────────────────

@router.get("/preferences", response_model=list[NotificationPreferenceResponse])
async def list_preferences(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all notification preferences for the current user."""
    result = await db.execute(
        select(NotificationPreference)
        .where(NotificationPreference.user_id == current_user.id)
        .order_by(NotificationPreference.channel, NotificationPreference.project_id)
    )
    return result.scalars().all()


@router.post(
    "/preferences",
    response_model=NotificationPreferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_preference(
    payload: NotificationPreferenceCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create or replace a notification preference for a specific channel.
    The combination (user_id, project_id, channel) is unique — this upserts.
    """
    # Check for existing preference
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user.id,
            NotificationPreference.project_id == payload.project_id,
            NotificationPreference.channel == payload.channel,
        )
    )
    pref = result.scalar_one_or_none()

    if pref:
        pref.enabled = payload.enabled
        pref.events = payload.events
        pref.failure_rate_threshold = payload.failure_rate_threshold
        pref.email_override = payload.email_override
        pref.slack_webhook_url = payload.slack_webhook_url
        pref.teams_webhook_url = payload.teams_webhook_url
    else:
        pref = NotificationPreference(
            user_id=current_user.id,
            project_id=payload.project_id,
            channel=payload.channel,
            enabled=payload.enabled,
            events=payload.events,
            failure_rate_threshold=payload.failure_rate_threshold,
            email_override=payload.email_override,
            slack_webhook_url=payload.slack_webhook_url,
            teams_webhook_url=payload.teams_webhook_url,
        )
        db.add(pref)

    await db.commit()
    await db.refresh(pref)
    return pref


@router.put("/preferences/{pref_id}", response_model=NotificationPreferenceResponse)
async def update_preference(
    pref_id: uuid.UUID,
    payload: NotificationPreferenceCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a specific notification preference by ID."""
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.id == pref_id,
            NotificationPreference.user_id == current_user.id,
        )
    )
    pref = result.scalar_one_or_none()
    if not pref:
        raise HTTPException(status_code=404, detail="Preference not found")

    pref.enabled = payload.enabled
    pref.events = payload.events
    pref.failure_rate_threshold = payload.failure_rate_threshold
    pref.email_override = payload.email_override
    pref.slack_webhook_url = payload.slack_webhook_url
    pref.teams_webhook_url = payload.teams_webhook_url

    await db.commit()
    await db.refresh(pref)
    return pref


@router.delete("/preferences/{pref_id}", status_code=204)
async def delete_preference(
    pref_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a notification preference."""
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.id == pref_id,
            NotificationPreference.user_id == current_user.id,
        )
    )
    pref = result.scalar_one_or_none()
    if not pref:
        raise HTTPException(status_code=404, detail="Preference not found")
    await db.delete(pref)
    await db.commit()


# ── Notification history ──────────────────────────────────────

@router.get("/history", response_model=list[NotificationLogResponse])
async def list_history(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Return recent notification log entries for the current user."""
    query = (
        select(NotificationLog)
        .where(NotificationLog.user_id == current_user.id)
        .order_by(NotificationLog.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        query = query.where(NotificationLog.is_read.is_(False))

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/history/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Return count of unread notifications for the bell badge."""
    from sqlalchemy import func
    result = await db.execute(
        select(func.count(NotificationLog.id)).where(
            NotificationLog.user_id == current_user.id,
            NotificationLog.is_read.is_(False),
        )
    )
    count = result.scalar() or 0
    return {"unread": count}


@router.post("/history/{log_id}/read", status_code=204)
async def mark_read(
    log_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a single notification as read."""
    await db.execute(
        update(NotificationLog)
        .where(
            NotificationLog.id == log_id,
            NotificationLog.user_id == current_user.id,
        )
        .values(is_read=True)
    )
    await db.commit()


@router.post("/history/read-all", status_code=204)
async def mark_all_read(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    await db.execute(
        update(NotificationLog)
        .where(
            NotificationLog.user_id == current_user.id,
            NotificationLog.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await db.commit()


# ── Test notifications ────────────────────────────────────────

@router.post("/test")
async def send_test(
    payload: TestNotificationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a test notification to verify channel configuration.
    If preference_id is provided, uses that preference's webhook/email settings.
    """
    email_override = None
    slack_webhook_url = None
    teams_webhook_url = None

    if payload.preference_id:
        result = await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.id == payload.preference_id,
                NotificationPreference.user_id == current_user.id,
            )
        )
        pref = result.scalar_one_or_none()
        if pref:
            email_override = pref.email_override
            slack_webhook_url = pref.slack_webhook_url
            teams_webhook_url = pref.teams_webhook_url

    status_str, error = await send_test_notification(
        user_id=current_user.id,
        channel=payload.channel,
        email_override=email_override,
        slack_webhook_url=slack_webhook_url,
        teams_webhook_url=teams_webhook_url,
    )

    if status_str == "failed":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Test notification failed: {error}",
        )

    return {"status": "sent", "channel": payload.channel}
