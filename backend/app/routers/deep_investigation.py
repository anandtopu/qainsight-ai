"""
Deep Investigation Router.
Triggers the deep analysis pipeline and exposes cluster/finding results.
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import get_current_active_user
from app.db.postgres import AsyncSessionLocal
from app.models.postgres import (
    DeepFinding,
    FailureCluster,
    TestRun,
    User,
)
from app.worker.tasks import run_agent_pipeline

logger = logging.getLogger("routers.deep_investigation")

router = APIRouter(prefix="/api/v1/deep-investigate", tags=["Deep Investigation"])


class TriggerDeepRequest(BaseModel):
    mode: str = "deep"  # "deep" | "offline"


class TriggerDeepResponse(BaseModel):
    pipeline_run_id: Optional[str] = None
    message: str
    run_id: str


class ClusterResponse(BaseModel):
    cluster_id: str
    label: str
    representative_error: Optional[str]
    member_test_ids: list[str]
    size: int
    cohesion_score: Optional[float] = None


class DeepFindingResponse(BaseModel):
    cluster_id: str
    root_cause: Optional[str]
    failure_category: Optional[str]
    confidence_score: Optional[int]
    causal_chain: Optional[list]
    evidence: Optional[list]
    affected_services: Optional[list]
    contract_violations: Optional[list]
    recommended_actions: Optional[list]


@router.post("/{run_id}", response_model=TriggerDeepResponse)
async def trigger_deep_investigation(
    run_id: uuid.UUID,
    body: TriggerDeepRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Trigger the deep investigation pipeline for a completed test run.
    Uses workflow_type="deep" which adds failure clustering, flaky sentinel,
    test health analysis, and release risk on top of the standard 5-stage pipeline.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(TestRun).where(TestRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run not found")

    workflow_type = body.mode if body.mode in ("deep", "offline") else "deep"

    try:
        task = run_agent_pipeline.apply_async(
            kwargs={
                "test_run_id": str(run_id),
                "project_id": str(run.project_id),
                "build_number": run.build_number,
                "workflow_type": workflow_type,
            },
            queue="ai_analysis",
        )
        return TriggerDeepResponse(
            pipeline_run_id=task.id,
            message=f"Deep investigation pipeline queued (mode={workflow_type})",
            run_id=str(run_id),
        )
    except Exception as exc:
        logger.error("Failed to queue deep pipeline for run %s: %s", run_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/{run_id}/clusters", response_model=list[ClusterResponse])
async def get_failure_clusters(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Return semantic failure clusters for a test run."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FailureCluster)
            .where(FailureCluster.test_run_id == run_id)
            .order_by(FailureCluster.size.desc())
        )
        clusters = result.scalars().all()

    return [
        ClusterResponse(
            cluster_id=c.cluster_id,
            label=c.label,
            representative_error=c.representative_error,
            member_test_ids=c.member_test_ids or [],
            size=c.size,
            cohesion_score=c.cohesion_score,
        )
        for c in clusters
    ]


@router.get("/{run_id}/findings", response_model=list[DeepFindingResponse])
async def get_deep_findings(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Return deep investigation findings per failure cluster for a test run."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DeepFinding)
            .where(DeepFinding.test_run_id == run_id)
        )
        findings = result.scalars().all()

    return [
        DeepFindingResponse(
            cluster_id=f.cluster_id,
            root_cause=f.root_cause,
            failure_category=f.failure_category,
            confidence_score=f.confidence_score,
            causal_chain=f.causal_chain,
            evidence=f.evidence,
            affected_services=f.affected_services,
            contract_violations=f.contract_violations,
            recommended_actions=f.recommended_actions,
        )
        for f in findings
    ]
