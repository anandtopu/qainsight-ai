"""
LangGraph workflow orchestration for the multi-agent pipeline.

Defines two compiled workflows:
  • offline_pipeline — processes a completed test run through 5 stages
  • (live monitoring is handled by LiveMonitorAgent separately)

Each workflow node is an async function wrapping the corresponding agent.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from langgraph.graph import END, StateGraph  # type: ignore

from app.agents.analysis_agent import AnalysisAgent
from app.agents.anomaly_agent import AnomalyDetectionAgent
from app.agents.ingestion_agent import IngestionAgent
from app.agents.state import WorkflowState
from app.agents.summary_agent import SummaryAgent
from app.agents.triage_agent import DefectTriageAgent
from app.db.postgres import AsyncSessionLocal
from app.models.postgres import AgentPipelineRun, AgentStageResult

logger = logging.getLogger("agents.workflow")

# Singleton agent instances (stateless — safe to share)
_ingestion = IngestionAgent()
_anomaly = AnomalyDetectionAgent()
_analysis = AnalysisAgent()
_summary = SummaryAgent()
_triage = DefectTriageAgent()


# ── LangGraph node functions ──────────────────────────────────────

async def ingestion_node(state: WorkflowState) -> dict:
    return await _ingestion.run(state)


async def anomaly_node(state: WorkflowState) -> dict:
    return await _anomaly.run(state)


async def analysis_node(state: WorkflowState) -> dict:
    return await _analysis.run(state)


async def summary_node(state: WorkflowState) -> dict:
    return await _summary.run(state)


async def triage_node(state: WorkflowState) -> dict:
    return await _triage.run(state)


# ── Graph construction ────────────────────────────────────────────

def _build_offline_graph() -> StateGraph:
    graph = StateGraph(WorkflowState)

    graph.add_node("ingestion", ingestion_node)
    graph.add_node("anomaly_detection", anomaly_node)
    graph.add_node("root_cause_analysis", analysis_node)
    graph.add_node("summary", summary_node)
    graph.add_node("triage", triage_node)

    graph.set_entry_point("ingestion")
    graph.add_edge("ingestion", "anomaly_detection")
    graph.add_edge("anomaly_detection", "root_cause_analysis")
    graph.add_edge("root_cause_analysis", "summary")
    graph.add_edge("summary", "triage")
    graph.add_edge("triage", END)

    return graph


# Compile once at module load
_offline_app = _build_offline_graph().compile()


# ── Public entry point ────────────────────────────────────────────

async def run_offline_pipeline(
    test_run_id: str,
    project_id: str,
    build_number: str,
    workflow_type: str = "offline",
) -> dict:
    """
    Execute the full offline analysis pipeline for a completed test run.

    Creates an AgentPipelineRun record, builds the initial state, runs the
    LangGraph workflow, and returns the final state.
    """
    pipeline_run_id = str(uuid.uuid4())

    # Create DB tracking records
    await _create_pipeline_run(pipeline_run_id, test_run_id, workflow_type)

    initial_state: WorkflowState = {
        "pipeline_run_id": pipeline_run_id,
        "test_run_id": test_run_id,
        "project_id": project_id,
        "build_number": build_number,
        "workflow_type": workflow_type,
        # Stage outputs (initialised empty)
        "test_run_data": None,
        "failed_test_ids": [],
        "total_tests": 0,
        "pass_rate": 0.0,
        "ingestion_enriched": False,
        "anomalies": [],
        "is_regression": False,
        "regression_tests": [],
        "anomaly_summary": None,
        "analyses": {},
        "executive_summary": None,
        "summary_markdown": None,
        "triage_results": [],
        "errors": [],
        "completed_stages": [],
        "current_stage": "ingestion",
    }

    try:
        logger.info(
            "Starting offline pipeline %s for run %s (build=%s)",
            pipeline_run_id, test_run_id, build_number,
        )
        final_state = await _offline_app.ainvoke(initial_state)
        await _mark_pipeline_done(pipeline_run_id, success=True)
        logger.info(
            "Pipeline %s complete. stages=%s errors=%d",
            pipeline_run_id,
            final_state.get("completed_stages"),
            len(final_state.get("errors", [])),
        )
        return final_state
    except Exception as exc:
        error_msg = f"Pipeline execution error: {exc}"
        logger.error(error_msg, exc_info=True)
        await _mark_pipeline_done(pipeline_run_id, success=False, error=error_msg)
        raise


# ── DB helpers ────────────────────────────────────────────────────

_PIPELINE_STAGES = ["ingestion", "anomaly_detection", "root_cause_analysis", "summary", "triage"]


async def _create_pipeline_run(
    pipeline_run_id: str, test_run_id: str, workflow_type: str
) -> None:
    async with AsyncSessionLocal() as db:
        pipeline_run = AgentPipelineRun(
            id=pipeline_run_id,
            test_run_id=test_run_id,
            workflow_type=workflow_type,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(pipeline_run)

        for stage in _PIPELINE_STAGES:
            db.add(AgentStageResult(
                pipeline_run_id=pipeline_run_id,
                stage_name=stage,
                status="pending",
            ))

        await db.commit()


async def _mark_pipeline_done(
    pipeline_run_id: str, success: bool, error: Optional[str] = None
) -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(AgentPipelineRun).where(AgentPipelineRun.id == pipeline_run_id)
        )
        run = result.scalar_one_or_none()
        if run:
            run.status = "completed" if success else "failed"
            run.completed_at = datetime.now(timezone.utc)
            if error:
                run.error = error[:2000]
            await db.commit()
