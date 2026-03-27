"""
Agent pipeline management endpoints.

Provides visibility into running/completed pipelines and allows manual triggering.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user, require_role
from app.db.postgres import get_db
from app.models.postgres import AgentPipelineRun, AgentStageResult, TestRun, UserRole
from app.models.schemas import AgentPipelineResponse, TriggerPipelineRequest

router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])


@router.get("/pipelines", response_model=list[AgentPipelineResponse])
async def list_pipelines(
    run_id: Optional[uuid.UUID] = Query(None),
    project_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: any = Depends(get_current_active_user),
):
    """List agent pipeline runs, optionally filtered by test run, project, or status."""
    q = select(AgentPipelineRun)
    if run_id:
        q = q.where(AgentPipelineRun.test_run_id == run_id)
    if project_id:
        q = q.join(TestRun, AgentPipelineRun.test_run_id == TestRun.id).where(
            TestRun.project_id == project_id
        )
    if status:
        q = q.where(AgentPipelineRun.status == status)
    q = q.order_by(AgentPipelineRun.created_at.desc()).limit(limit)

    result = await db.execute(q)
    return result.scalars().all()


@router.get("/pipelines/{pipeline_id}", response_model=AgentPipelineResponse)
async def get_pipeline(
    pipeline_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: any = Depends(get_current_active_user),
):
    """Get a single pipeline run with all stage results."""
    result = await db.execute(
        select(AgentPipelineRun).where(AgentPipelineRun.id == pipeline_id)
    )
    pipeline = result.scalar_one_or_none()
    if not pipeline:
        raise HTTPException(404, detail="Pipeline run not found")
    return pipeline


@router.post("/pipelines/trigger", status_code=202)
async def trigger_pipeline(
    payload: TriggerPipelineRequest,
    db: AsyncSession = Depends(get_db),
    _: any = Depends(require_role(UserRole.QA_ENGINEER)),
):
    """
    Manually trigger the agent pipeline for an existing test run.
    Returns 202 Accepted — pipeline runs asynchronously via Celery.
    """
    # Verify the run exists
    run_result = await db.execute(select(TestRun).where(TestRun.id == payload.test_run_id))
    run = run_result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, detail="TestRun not found")

    from app.worker.tasks import run_agent_pipeline
    task = run_agent_pipeline.delay(
        test_run_id=str(run.id),
        project_id=str(run.project_id),
        build_number=run.build_number,
        workflow_type="offline",
    )

    return {"message": "Pipeline queued", "task_id": task.id, "run_id": str(run.id)}


@router.get("/pipelines/{pipeline_id}/stages", response_model=list[dict])
async def get_pipeline_stages(
    pipeline_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: any = Depends(get_current_active_user),
):
    """Get detailed stage results for a pipeline run."""
    result = await db.execute(
        select(AgentStageResult)
        .where(AgentStageResult.pipeline_run_id == pipeline_id)
        .order_by(AgentStageResult.started_at)
    )
    stages = result.scalars().all()
    return [
        {
            "stage_name": s.stage_name,
            "status": s.status,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "result_data": s.result_data,
            "error": s.error,
        }
        for s in stages
    ]


@router.get("/active-runs")
async def get_active_live_runs(_: any = Depends(get_current_active_user)):
    """Get all currently monitored live test runs."""
    from app.agents.live_monitor import LiveMonitorAgent
    return {"active_runs": await LiveMonitorAgent.get_active_runs()}


@router.get("/active-runs/{run_id}")
async def get_live_run_state(
    run_id: str,
    _: any = Depends(get_current_active_user),
):
    """Get the current state for a single live test run."""
    from app.agents.live_monitor import LiveMonitorAgent
    state = await LiveMonitorAgent.get_run_state(run_id)
    if not state:
        raise HTTPException(404, detail="Live run not found or already completed")
    return state


@router.get("/runs/{run_id}/summary")
async def get_run_summary(
    run_id: str,
    _: any = Depends(get_current_active_user),
):
    """Retrieve the AI-generated markdown summary for a test run."""
    from app.db.mongo import Collections, get_mongo_db
    db = get_mongo_db()
    doc = await db[Collections.RUN_SUMMARIES].find_one({"test_run_id": run_id})
    if not doc:
        raise HTTPException(404, detail="No summary found for this run")
    doc.pop("_id", None)
    return doc
