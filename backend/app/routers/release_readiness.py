"""
Release Readiness Router.
Exposes go/no-go release decisions produced by ReleaseRiskAgent.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import get_current_active_user, require_role
from app.db.postgres import AsyncSessionLocal
from app.models.postgres import ReleaseDecision, TestRun, User, UserRole

logger = logging.getLogger("routers.release_readiness")

router = APIRouter(prefix="/api/v1/release-readiness", tags=["Release Readiness"])


class ReleaseDecisionResponse(BaseModel):
    run_id: str
    recommendation: str          # GO | NO_GO | CONDITIONAL_GO
    risk_score: int
    blocking_issues: list[str]
    conditions_for_go: list[str]
    reasoning: Optional[str]
    human_override: Optional[str]
    pass_rate: Optional[float] = None
    build_number: Optional[str] = None


class OverrideRequest(BaseModel):
    override_recommendation: str   # GO | NO_GO | CONDITIONAL_GO
    reason: str


@router.get("/{run_id}", response_model=ReleaseDecisionResponse)
async def get_release_decision(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve the latest release readiness decision for a test run.
    Returns 404 if the deep pipeline has not yet completed for this run.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ReleaseDecision).where(ReleaseDecision.test_run_id == run_id)
        )
        decision = result.scalar_one_or_none()
        if not decision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No release decision found. Trigger deep investigation first.",
            )

        run_result = await db.execute(select(TestRun).where(TestRun.id == run_id))
        run = run_result.scalar_one_or_none()

    return ReleaseDecisionResponse(
        run_id=str(run_id),
        recommendation=decision.recommendation,
        risk_score=decision.risk_score,
        blocking_issues=decision.blocking_issues or [],
        conditions_for_go=decision.conditions_for_go or [],
        reasoning=decision.reasoning,
        human_override=decision.human_override,
        pass_rate=run.pass_rate if run else None,
        build_number=run.build_number if run else None,
    )


@router.post("/{run_id}/override", response_model=ReleaseDecisionResponse)
async def override_release_decision(
    run_id: str,
    body: OverrideRequest,
    current_user: User = Depends(require_role(UserRole.QA_LEAD)),
):
    """
    Override the AI release decision (QA Lead only).
    Records the override reason and the overriding user.
    """
    if body.override_recommendation not in ("GO", "NO_GO", "CONDITIONAL_GO"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="override_recommendation must be GO, NO_GO, or CONDITIONAL_GO",
        )

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ReleaseDecision).where(ReleaseDecision.test_run_id == run_id)
        )
        decision = result.scalar_one_or_none()
        if not decision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No release decision found for this run.",
            )

        decision.recommendation = body.override_recommendation
        decision.human_override = body.reason
        decision.overridden_by = current_user.id
        await db.commit()
        await db.refresh(decision)

        run_result = await db.execute(select(TestRun).where(TestRun.id == run_id))
        run = run_result.scalar_one_or_none()

    logger.info(
        "Release decision overridden for run %s by user %s: %s",
        run_id, current_user.username, body.override_recommendation,
    )

    return ReleaseDecisionResponse(
        run_id=str(run_id),
        recommendation=decision.recommendation,
        risk_score=decision.risk_score,
        blocking_issues=decision.blocking_issues or [],
        conditions_for_go=decision.conditions_for_go or [],
        reasoning=decision.reasoning,
        human_override=decision.human_override,
        pass_rate=run.pass_rate if run else None,
        build_number=run.build_number if run else None,
    )
