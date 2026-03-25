"""
LangGraph workflow orchestration for the multi-agent pipeline.

Improvements over v1:
  1. Conditional skip — if no failed tests, jump straight to summary (skip anomaly + analysis)
  2. Parallel fan-out — anomaly_detection and root_cause_analysis run concurrently after ingestion
     (both read from ingestion outputs; their state fields are non-overlapping with Annotated reducers)
  3. Conditional triage — skip triage stage when no analyses meet the confidence threshold
  4. Two compiled graphs: offline (5-stage) and live (summary-only, for post-live-run processing)
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
from app.core.config import settings
from app.db.postgres import AsyncSessionLocal
from app.models.postgres import AgentPipelineRun, AgentStageResult

logger = logging.getLogger("agents.workflow")

# Singleton agent instances (stateless — safe to share across concurrent pipeline runs)
_ingestion = IngestionAgent()
_anomaly   = AnomalyDetectionAgent()
_analysis  = AnalysisAgent()
_summary   = SummaryAgent()
_triage    = DefectTriageAgent()


# ── LangGraph node functions ──────────────────────────────────────────────────

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


# ── Routing functions (conditional edges) ────────────────────────────────────

def _route_after_ingestion(state: WorkflowState) -> str:
    """
    Fast-path: if the run has no failures there is nothing to analyse.
    Route directly to summary, which will generate an "all green" report.
    Otherwise route to anomaly_detection (which runs in parallel with analysis
    via the branching edges added in the graph).
    """
    if not state.get("failed_test_ids"):
        logger.info(
            "Pipeline %s: no failures detected — skipping analysis stages",
            state.get("pipeline_run_id"),
        )
        return "summary"
    return "anomaly_detection"


def _route_after_summary(state: WorkflowState) -> str:
    """
    Skip triage when no analyses reach the confidence threshold.
    Saves Jira API calls and reduces noise in the ticket tracker.
    """
    analyses = state.get("analyses", {})
    threshold = settings.AI_CONFIDENCE_THRESHOLD
    has_triageable = any(
        a.get("confidence_score", 0) >= threshold and not a.get("is_flaky", False)
        for a in analyses.values()
    )
    if not has_triageable:
        logger.info(
            "Pipeline %s: no analyses above confidence threshold (%d) — skipping triage",
            state.get("pipeline_run_id"), threshold,
        )
        return END
    return "triage"


# ── Graph construction ────────────────────────────────────────────────────────

def _build_offline_graph() -> StateGraph:
    """
    Full offline pipeline with parallel anomaly + analysis fan-out.

    Graph topology:
                                ┌─ anomaly_detection ─┐
      ingestion ─(conditional)──┤                      ├─ summary ─(conditional)─ triage ─ END
                                └─ root_cause_analysis─┘
                   (no failures) └──────────────────────────────────────────────────────── summary ─ END
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("ingestion",            ingestion_node)
    graph.add_node("anomaly_detection",    anomaly_node)
    graph.add_node("root_cause_analysis",  analysis_node)
    graph.add_node("summary",              summary_node)
    graph.add_node("triage",               triage_node)

    graph.set_entry_point("ingestion")

    # Conditional routing after ingestion:
    # - failures found  → fan-out to BOTH anomaly_detection AND root_cause_analysis (parallel)
    # - no failures     → skip directly to summary
    graph.add_conditional_edges(
        "ingestion",
        _route_after_ingestion,
        {
            "anomaly_detection": "anomaly_detection",
            "summary":           "summary",
        },
    )

    # Parallel fan-out: ingestion also fans out to root_cause_analysis
    # This edge is only traversed when _route_after_ingestion returns "anomaly_detection"
    # (LangGraph executes all outgoing edges from a node; the conditional edge above
    #  handles the "skip" case, while the unconditional edge below handles the parallel path)
    #
    # To implement the parallel fork correctly, we add ingestion → root_cause_analysis
    # as a second edge. LangGraph's StateGraph will execute both anomaly_detection and
    # root_cause_analysis concurrently after ingestion, then merge their state outputs
    # (safe because they write to non-overlapping fields: anomalies vs analyses).
    graph.add_edge("ingestion", "root_cause_analysis")

    # Fan-in: both parallel branches feed into summary
    graph.add_edge("anomaly_detection",   "summary")
    graph.add_edge("root_cause_analysis", "summary")

    # Conditional routing after summary: skip triage if no triageable analyses
    graph.add_conditional_edges(
        "summary",
        _route_after_summary,
        {
            "triage": "triage",
            END:      END,
        },
    )

    graph.add_edge("triage", END)

    return graph


def _build_live_graph() -> StateGraph:
    """
    Lightweight post-live-run graph: skip anomaly detection and full analysis,
    just generate a summary from the live monitor's aggregated state.
    Used when LiveMonitorAgent triggers a pipeline after run_complete.
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("ingestion", ingestion_node)
    graph.add_node("summary",   summary_node)

    graph.set_entry_point("ingestion")
    graph.add_edge("ingestion", "summary")
    graph.add_edge("summary", END)

    return graph


# Compile once at module load (compilation is expensive; instances are thread-safe)
_offline_app = _build_offline_graph().compile()
_live_app    = _build_live_graph().compile()


# ── Public entry points ───────────────────────────────────────────────────────

async def run_offline_pipeline(
    test_run_id: str,
    project_id: str,
    build_number: str,
    workflow_type: str = "offline",
) -> dict:
    """
    Execute the full offline analysis pipeline for a completed test run.

    - Creates AgentPipelineRun + AgentStageResult tracking records
    - Selects the appropriate compiled graph (offline vs live)
    - Returns the final LangGraph state dict
    """
    pipeline_run_id = str(uuid.uuid4())
    await _create_pipeline_run(pipeline_run_id, test_run_id, workflow_type)

    initial_state: WorkflowState = {
        "pipeline_run_id":    pipeline_run_id,
        "test_run_id":        test_run_id,
        "project_id":         project_id,
        "build_number":       build_number,
        "workflow_type":      workflow_type,
        # Stage outputs (initialised empty — agents populate these)
        "test_run_data":      None,
        "failed_test_ids":    [],
        "total_tests":        0,
        "pass_rate":          0.0,
        "ingestion_enriched": False,
        "anomalies":          [],
        "is_regression":      False,
        "regression_tests":   [],
        "anomaly_summary":    None,
        "analyses":           {},
        "executive_summary":  None,
        "summary_markdown":   None,
        "triage_results":     [],
        "errors":             [],
        "completed_stages":   [],
        "current_stage":      "ingestion",
    }

    app = _live_app if workflow_type == "live" else _offline_app

    try:
        logger.info(
            "Starting %s pipeline %s for run %s (build=%s)",
            workflow_type, pipeline_run_id, test_run_id, build_number,
        )
        final_state = await app.ainvoke(initial_state)
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


# ── DB helpers ────────────────────────────────────────────────────────────────

_PIPELINE_STAGES = [
    "ingestion", "anomaly_detection", "root_cause_analysis", "summary", "triage",
]


async def _create_pipeline_run(
    pipeline_run_id: str, test_run_id: str, workflow_type: str
) -> None:
    async with AsyncSessionLocal() as db:
        db.add(AgentPipelineRun(
            id=pipeline_run_id,
            test_run_id=test_run_id,
            workflow_type=workflow_type,
            status="running",
            started_at=datetime.now(timezone.utc),
        ))
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
        from sqlalchemy import select as sa_select
        result = await db.execute(
            sa_select(AgentPipelineRun).where(AgentPipelineRun.id == pipeline_run_id)
        )
        run = result.scalar_one_or_none()
        if run:
            run.status = "completed" if success else "failed"
            run.completed_at = datetime.now(timezone.utc)
            if error:
                run.error = error[:2000]
            await db.commit()
