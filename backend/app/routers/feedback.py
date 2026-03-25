"""
AI feedback endpoints — capture human signals for continuous fine-tuning.

POST /api/v1/feedback/{analysis_id}      — rate an AI analysis result
PUT  /api/v1/feedback/{analysis_id}      — update a previously submitted rating
GET  /api/v1/feedback/stats              — feedback summary for dashboard
POST /api/v1/training/export             — manually trigger training data export
POST /api/v1/training/promote            — manually promote a fine-tuned model
GET  /api/v1/training/status             — model registry + pending example counts
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user, require_role
from app.db.postgres import get_db
from app.models.postgres import (
    AIAnalysis,
    AIFeedback,
    FeedbackRating,
    FailureCategory,
    UserRole,
)

router = APIRouter(prefix="/api/v1", tags=["Feedback & Training"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    rating: FeedbackRating
    corrected_category: Optional[FailureCategory] = None
    corrected_root_cause: Optional[str] = None
    comment: Optional[str] = None


class PromoteModelRequest(BaseModel):
    track: str           # "classifier" | "reasoning" | "embedding"
    model_name: str
    eval_accuracy: Optional[float] = None
    baseline_accuracy: Optional[float] = None


# ── Feedback endpoints ────────────────────────────────────────────────────────

@router.post("/feedback/{analysis_id}", status_code=201)
async def submit_feedback(
    analysis_id: uuid.UUID,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Submit feedback on an AI triage analysis result.
    This is the primary mechanism for human-in-the-loop quality signals.
    """
    result = await db.execute(select(AIAnalysis).where(AIAnalysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, detail="Analysis not found")

    feedback = AIFeedback(
        analysis_id=analysis_id,
        test_case_id=analysis.test_case_id,
        user_id=current_user.id,
        rating=body.rating,
        corrected_category=body.corrected_category,
        corrected_root_cause=body.corrected_root_cause,
        comment=body.comment,
        source="manual",
        exported=False,
    )
    db.add(feedback)

    # If engineer provided a corrected category, back-propagate to AIAnalysis immediately
    if body.corrected_category and body.rating == FeedbackRating.INCORRECT:
        analysis.failure_category = body.corrected_category
        if body.corrected_root_cause:
            analysis.root_cause_summary = body.corrected_root_cause
        analysis.requires_human_review = False

    await db.commit()
    return {"feedback_id": str(feedback.id), "message": "Feedback recorded — thank you!"}


@router.put("/feedback/{analysis_id}", status_code=200)
async def update_feedback(
    analysis_id: uuid.UUID,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Update an existing feedback entry (e.g., engineer changes their mind)."""
    result = await db.execute(
        select(AIFeedback)
        .where(AIFeedback.analysis_id == analysis_id)
        .where(AIFeedback.user_id == current_user.id)
        .where(AIFeedback.source == "manual")
        .order_by(AIFeedback.created_at.desc())
        .limit(1)
    )
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(404, detail="No feedback found for this analysis from current user")

    feedback.rating = body.rating
    feedback.corrected_category = body.corrected_category
    feedback.corrected_root_cause = body.corrected_root_cause
    feedback.comment = body.comment
    feedback.exported = False  # re-export with corrected label
    await db.commit()
    return {"message": "Feedback updated"}


@router.get("/feedback/stats")
async def get_feedback_stats(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """Return feedback counts by rating for the dashboard."""
    rows = await db.execute(
        select(AIFeedback.rating, func.count(AIFeedback.id))
        .group_by(AIFeedback.rating)
    )
    counts = {str(row[0]): row[1] for row in rows.all()}

    total_result = await db.execute(select(func.count(AIFeedback.id)))
    total = total_result.scalar_one()

    unexported_result = await db.execute(
        select(func.count(AIFeedback.id)).where(AIFeedback.exported.is_(False))
    )
    unexported = unexported_result.scalar_one()

    return {
        "total_feedback": total,
        "unexported": unexported,
        "by_rating": counts,
    }


# ── Training management endpoints ─────────────────────────────────────────────

@router.post("/training/export", status_code=202)
async def trigger_export(
    _=Depends(require_role(UserRole.QA_LEAD)),
):
    """Manually trigger training data export to MinIO (normally runs weekly)."""
    from app.worker.training_tasks import export_training_data
    task = export_training_data.apply_async(queue="default")
    return {"message": "Training data export queued", "task_id": task.id}


@router.post("/training/finetune", status_code=202)
async def trigger_finetune(
    track: str = Body(..., embed=True),
    _=Depends(require_role(UserRole.QA_LEAD)),
):
    """Manually trigger fine-tuning for a specific track."""
    if track not in ("classifier", "reasoning", "embedding"):
        raise HTTPException(400, detail="track must be classifier | reasoning | embedding")
    from app.worker.training_tasks import run_finetune_pipeline
    task = run_finetune_pipeline.apply_async(kwargs={"track": track}, queue="default")
    return {"message": f"Fine-tuning queued for track={track}", "task_id": task.id}


@router.post("/training/promote", status_code=200)
async def promote_model(
    body: PromoteModelRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(UserRole.ADMIN)),
):
    """
    Manually promote a fine-tuned model to active.
    Use this after external fine-tuning (e.g., Unsloth) to hot-swap the model.
    """
    from app.services.model_registry import ModelRegistry
    from app.models.postgres import ModelVersion
    from datetime import datetime, timezone

    await ModelRegistry.promote(
        track=body.track,
        model_name=body.model_name,
        metrics={
            "eval_accuracy": body.eval_accuracy,
            "baseline_accuracy": body.baseline_accuracy,
            "promoted_by": "manual",
        },
    )

    # Persist to model_versions table for audit trail
    version = ModelVersion(
        track=body.track,
        model_name=body.model_name,
        provider=settings_provider(),
        status="active",
        eval_accuracy=body.eval_accuracy,
        baseline_accuracy=body.baseline_accuracy,
        promoted_at=datetime.now(timezone.utc),
    )
    db.add(version)
    await db.commit()

    return {"message": f"Model {body.model_name} promoted for track={body.track}"}


@router.get("/training/status")
async def get_training_status(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """Model registry status + feedback counts + example thresholds."""
    from app.services.model_registry import ModelRegistry
    from app.core.config import settings

    registry = await ModelRegistry.get_all_status()

    unexported_result = await db.execute(
        select(func.count(AIFeedback.id)).where(AIFeedback.exported.is_(False))
    )
    unexported = unexported_result.scalar_one()

    total_result = await db.execute(select(func.count(AIFeedback.id)))
    total = total_result.scalar_one()

    return {
        "finetune_enabled": settings.FINETUNE_ENABLED,
        "feedback": {
            "total": total,
            "unexported": unexported,
        },
        "thresholds": {
            "classifier": settings.FINETUNE_CLASSIFIER_MIN_EXAMPLES,
            "reasoning": settings.FINETUNE_REASONING_MIN_EXAMPLES,
            "embedding": settings.FINETUNE_EMBED_MIN_PAIRS,
            "incremental_retrigger": settings.FINETUNE_INCREMENTAL_TRIGGER,
        },
        "active_models": registry,
    }


@router.post("/feedback/jira-webhook", status_code=200)
async def jira_resolution_webhook(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Jira webhook receiver — auto-creates implicit feedback when issues are resolved.

    Configure in Jira:
      URL: POST https://your-backend/api/v1/feedback/jira-webhook
      Events: Issue Updated (when status transitions to Done/Resolved/Closed)

    This passively builds training signal without any manual engineer action.
    """
    issue_key = payload.get("issue", {}).get("key", "")
    status = (payload.get("issue", {}).get("fields", {}).get("status", {}).get("name", "")).lower()
    resolution = (payload.get("issue", {}).get("fields", {}).get("resolution", {}) or {}).get("name", "").lower()

    is_resolved = status in ("done", "resolved", "closed", "fixed")
    is_invalid = resolution in ("won't fix", "duplicate", "invalid", "not a bug", "cannot reproduce")

    if not is_resolved and not is_invalid:
        return {"message": "no action — not a resolution event"}

    # Find the defect by Jira ticket ID
    result = await db.execute(
        select(Defect).where(Defect.jira_ticket_id == issue_key)
    )
    defect = result.scalar_one_or_none()
    if not defect:
        return {"message": f"no defect found for {issue_key}"}

    from datetime import datetime, timezone
    defect.jira_status = status
    defect.resolution_status = "RESOLVED" if is_resolved else "INVALID"
    if is_resolved:
        defect.resolved_at = datetime.now(timezone.utc)

    # Create implicit feedback record
    ai_result = await db.execute(
        select(AIAnalysis).where(AIAnalysis.test_case_id == defect.test_case_id)
    )
    analysis = ai_result.scalar_one_or_none()
    if analysis:
        rating = FeedbackRating.INCORRECT if is_invalid else FeedbackRating.CORRECT
        source = "jira_invalid" if is_invalid else "jira_resolved"
        feedback = AIFeedback(
            analysis_id=analysis.id,
            test_case_id=defect.test_case_id,
            user_id=None,   # system-generated
            rating=rating,
            source=source,
            exported=False,
        )
        db.add(feedback)

    await db.commit()
    return {
        "message": f"Feedback recorded: {issue_key} → {rating if analysis else 'no analysis found'}",
        "defect_id": str(defect.id),
    }


def settings_provider() -> str:
    from app.core.config import settings
    return settings.LLM_PROVIDER
