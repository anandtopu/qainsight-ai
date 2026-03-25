"""
QA Insight AI — Prometheus custom application metrics.

Business-level metrics that complement the HTTP-level metrics emitted automatically
by prometheus-fastapi-instrumentator.

All metric objects are module-level singletons — import directly:
    from app.core.metrics import ingestion_runs_total, pipeline_stage_duration_seconds
"""
from prometheus_client import Counter, Gauge, Histogram, Info  # type: ignore

# ── Ingestion ─────────────────────────────────────────────────────────────────

ingestion_runs_total = Counter(
    "qainsight_ingestion_runs_total",
    "Total test-run ingestion tasks processed",
    ["status"],  # success | failure
)

ingestion_test_cases_total = Counter(
    "qainsight_ingestion_test_cases_total",
    "Total individual test cases ingested",
    ["framework", "status"],  # framework: allure|testng|junit; status: passed|failed|skipped
)

ingestion_duration_seconds = Histogram(
    "qainsight_ingestion_duration_seconds",
    "Wall-clock time for a complete test-run ingestion",
    buckets=[1, 5, 15, 30, 60, 120, 300],
)

# ── AI Pipeline ───────────────────────────────────────────────────────────────

ai_analyses_total = Counter(
    "qainsight_ai_analyses_total",
    "Total AI root-cause analysis pipeline runs completed",
    ["workflow_type", "status"],  # workflow_type: offline|deep; status: success|failure
)

ai_analysis_duration_seconds = Histogram(
    "qainsight_ai_analysis_duration_seconds",
    "Wall-clock time for a complete AI pipeline run",
    ["workflow_type"],
    buckets=[5, 15, 30, 60, 120, 300, 600],
)

active_pipeline_runs = Gauge(
    "qainsight_active_pipeline_runs",
    "Pipeline runs currently in progress",
    ["workflow_type"],
)

# ── Pipeline Stages ───────────────────────────────────────────────────────────

pipeline_stage_duration_seconds = Histogram(
    "qainsight_pipeline_stage_duration_seconds",
    "Duration of each individual agent stage",
    ["stage_name", "status"],  # status: completed|failed
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120],
)

pipeline_stage_runs_total = Counter(
    "qainsight_pipeline_stage_runs_total",
    "Total agent stage executions",
    ["stage_name", "status"],
)

# ── Release Gate ──────────────────────────────────────────────────────────────

release_decisions_total = Counter(
    "qainsight_release_decisions_total",
    "Total release gate decisions issued",
    ["recommendation"],  # GO | NO_GO | CONDITIONAL_GO
)

# ── LLM / Inference ───────────────────────────────────────────────────────────

llm_requests_total = Counter(
    "qainsight_llm_requests_total",
    "Total LLM inference calls made",
    ["provider", "status"],  # status: success|failure|timeout
)

llm_request_duration_seconds = Histogram(
    "qainsight_llm_request_duration_seconds",
    "LLM inference latency (wall-clock)",
    ["provider"],
    buckets=[1, 2, 5, 10, 30, 60, 120],
)

llm_circuit_breaker_trips_total = Counter(
    "qainsight_llm_circuit_breaker_trips_total",
    "Number of times the LLM circuit breaker transitioned to OPEN state",
)

# ── Celery ────────────────────────────────────────────────────────────────────

celery_tasks_total = Counter(
    "qainsight_celery_tasks_total",
    "Total Celery background tasks executed",
    ["task_name", "status"],  # status: success|failure|retry
)

celery_task_duration_seconds = Histogram(
    "qainsight_celery_task_duration_seconds",
    "Celery task wall-clock execution time",
    ["task_name"],
    buckets=[1, 5, 15, 30, 60, 300, 600],
)

# ── WebSocket ─────────────────────────────────────────────────────────────────

websocket_connections_active = Gauge(
    "qainsight_websocket_connections_active",
    "Number of active WebSocket connections (summed across all projects)",
)

# ── Service Metadata ──────────────────────────────────────────────────────────

app_info = Info(
    "qainsight_app",
    "QA Insight AI static application metadata",
)
