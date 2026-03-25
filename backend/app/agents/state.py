"""
LangGraph workflow state shared across all pipeline agents.
Each agent reads from and writes to this state as it moves through stages.
"""
from typing import Annotated, Optional
from typing_extensions import TypedDict


def _merge_dicts(a: dict, b: dict) -> dict:
    """Reducer: merge two dicts (used for parallel analysis fan-out)."""
    return {**a, **b}


def _concat_lists(a: list, b: list) -> list:
    """Reducer: concatenate lists across parallel nodes."""
    return a + b


class WorkflowState(TypedDict):
    # ── Required Inputs ───────────────────────────────────────────
    pipeline_run_id: str        # AgentPipelineRun.id (UUID string)
    test_run_id: str            # TestRun.id that triggered this pipeline
    project_id: str             # Project.id
    build_number: str
    workflow_type: str          # "offline" | "live"

    # ── Stage 1: Ingestion Agent ──────────────────────────────────
    test_run_data: Optional[dict]        # Serialized TestRun summary
    failed_test_ids: list[str]           # IDs of FAILED / BROKEN tests
    total_tests: int
    pass_rate: float
    ingestion_enriched: bool

    # ── Stage 2: Anomaly Detection Agent ─────────────────────────
    anomalies: list[dict]               # [{type, severity, description, test_ids}]
    is_regression: bool                 # Pass rate dropped significantly vs baseline
    regression_tests: list[str]         # Tests that newly failed this run
    anomaly_summary: Optional[str]      # Short human-readable summary

    # ── Stage 3: Root Cause Analysis Agent (parallel fan-out) ─────
    # Reducer merges results from parallel analysis nodes
    analyses: Annotated[dict[str, dict], _merge_dicts]   # test_case_id -> analysis dict

    # ── Stage 4: Summary Agent ────────────────────────────────────
    executive_summary: Optional[str]    # 2-3 sentence executive summary
    summary_markdown: Optional[str]     # Full markdown report

    # ── Stage 5: Defect Triage Agent ─────────────────────────────
    triage_results: list[dict]          # [{test_case_id, ticket_key, action: created|updated|skipped}]

    # ── Stage 2b: Failure Clustering (deep workflow only) ────────
    failure_clusters: list[dict]        # [{cluster_id, label, member_test_ids, representative_error, size}]
    cluster_map: dict[str, str]         # test_case_id -> cluster_id

    # ── Stage 3 deep: Deep Root-Cause per cluster ─────────────────
    deep_findings: Annotated[dict[str, dict], _merge_dicts]  # cluster_id -> DeepFinding dict

    # ── Stage: Flaky Sentinel ─────────────────────────────────────
    flaky_findings: list[dict]          # [{test_case_id, test_name, flaky_since_build, recommendation}]

    # ── Stage: Test Health ────────────────────────────────────────
    test_health_findings: list[dict]    # [{test_case_id, health_score, violations, recommendation}]

    # ── Stage 6: Release Risk Agent ──────────────────────────────
    release_decision: Optional[dict]    # {recommendation, risk_score, blocking_issues, reasoning}

    # ── Error / Progress Tracking ─────────────────────────────────
    errors: Annotated[list[str], _concat_lists]
    completed_stages: Annotated[list[str], _concat_lists]
    current_stage: str
