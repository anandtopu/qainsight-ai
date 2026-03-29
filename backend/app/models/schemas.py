"""Pydantic v2 request/response schemas for all API endpoints."""
import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.postgres import FailureCategory, LaunchStatus, NotificationChannel, Severity, TestStatus, UserRole


# ── Base ─────────────────────────────────────────────────────

class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: Optional[datetime] = None


# ── Auth Schemas ─────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None
    password: str = Field(..., min_length=8)


class UserResponse(TimestampMixin):
    id: uuid.UUID
    email: str
    username: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=12)


# ── Project Schemas ───────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = None
    jira_project_key: Optional[str] = None
    splunk_index: Optional[str] = None
    ocp_namespace: Optional[str] = None
    jenkins_job_pattern: Optional[str] = None


class ProjectResponse(TimestampMixin):
    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str] = None
    jira_project_key: Optional[str] = None
    ocp_namespace: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# ── Test Run Schemas ──────────────────────────────────────────

class TestRunSummary(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    build_number: str
    jenkins_job: Optional[str] = None
    trigger_source: Optional[str] = None
    branch: Optional[str] = None
    status: LaunchStatus
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    broken_tests: int
    pass_rate: Optional[float] = None
    duration_ms: Optional[int] = None
    ocp_pod_name: Optional[str] = None
    ocp_namespace: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestRunListResponse(BaseModel):
    items: List[TestRunSummary]
    total: int
    page: int
    size: int
    pages: int


# ── Test Case Schemas ─────────────────────────────────────────

class TestCaseSummary(BaseModel):
    id: uuid.UUID
    test_run_id: uuid.UUID
    test_name: str
    suite_name: Optional[str] = None
    class_name: Optional[str] = None
    status: TestStatus
    duration_ms: Optional[int] = None
    severity: Optional[Severity] = None
    feature: Optional[str] = None
    failure_category: Optional[FailureCategory] = None
    has_attachments: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestCaseDetail(TestCaseSummary):
    full_name: Optional[str] = None
    package_name: Optional[str] = None
    story: Optional[str] = None
    epic: Optional[str] = None
    owner: Optional[str] = None
    tags: Optional[List[str]] = None
    error_message: Optional[str] = None
    minio_s3_prefix: Optional[str] = None


class TestCaseListResponse(BaseModel):
    items: List[TestCaseSummary]
    total: int
    page: int
    size: int
    pages: int


# ── Metrics Schemas ───────────────────────────────────────────

class MetricCard(BaseModel):
    value: Any
    trend: Optional[float] = None  # Percentage change vs previous period
    trend_direction: Optional[str] = None  # "up" | "down" | "flat"


class DashboardSummary(BaseModel):
    total_executions_7d: MetricCard
    avg_pass_rate_7d: MetricCard
    active_defects: MetricCard
    flaky_test_count: MetricCard
    avg_duration_ms: MetricCard
    new_failures_24h: MetricCard
    coverage_pct: Optional[MetricCard] = None
    release_readiness: Optional[str] = None  # "GREEN" | "AMBER" | "RED"


class TrendDataPoint(BaseModel):
    date: str
    passed: int
    failed: int
    skipped: int
    broken: int
    total: int
    pass_rate: float


class TrendResponse(BaseModel):
    data: List[TrendDataPoint]
    period_days: int


# ── Webhook Schemas ───────────────────────────────────────────

class MinIOWebhookEvent(BaseModel):
    """MinIO ObjectCreated webhook payload."""
    EventName: str
    Key: str
    Records: Optional[List[dict]] = None


class SentinelFile(BaseModel):
    """upload_complete.json sentinel file content."""
    build_number: str
    project_id: str
    jenkins_job: Optional[str] = None
    trigger_source: Optional[str] = "push"
    branch: Optional[str] = None
    commit_hash: Optional[str] = None
    ocp_pod_name: Optional[str] = None
    ocp_namespace: Optional[str] = None
    # Optional: name of the software release this run belongs to.
    # If the release does not exist it is auto-created in "planning" status.
    release_name: Optional[str] = None


# ── AI Analysis Schemas ───────────────────────────────────────

class AnalyzeRequest(BaseModel):
    test_case_id: uuid.UUID
    service_name: Optional[str] = None
    timestamp: Optional[str] = None
    ocp_pod_name: Optional[str] = None
    ocp_namespace: Optional[str] = None


class EvidenceReference(BaseModel):
    source: str  # "splunk" | "stacktrace" | "ocp_events" | "flakiness"
    reference_id: str
    excerpt: str


class AnalysisResponse(BaseModel):
    test_case_id: uuid.UUID
    root_cause_summary: str
    failure_category: FailureCategory
    backend_error_found: bool
    pod_issue_found: bool
    is_flaky: bool
    confidence_score: int
    recommended_actions: List[str]
    evidence_references: List[EvidenceReference]
    llm_provider: str
    llm_model: str
    requires_human_review: bool


# ── Jira Integration Schemas ──────────────────────────────────

class JiraIssueRequest(BaseModel):
    project_key: str
    test_case_id: uuid.UUID
    test_name: str
    run_id: uuid.UUID
    ai_summary: str
    recommended_action: str


class JiraIssueResponse(BaseModel):
    ticket_id: str
    ticket_key: str
    ticket_url: str


# ── Search Schemas ────────────────────────────────────────────

class SearchRequest(BaseModel):
    q: str = Field(..., min_length=1)
    project_id: Optional[uuid.UUID] = None
    status: Optional[TestStatus] = None
    suite: Optional[str] = None
    days: Optional[int] = Field(None, ge=1, le=365)
    use_semantic: bool = False
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


class SearchResult(BaseModel):
    test_case_id: uuid.UUID
    test_run_id: uuid.UUID
    test_name: str
    suite_name: Optional[str] = None
    status: TestStatus
    last_run_date: datetime
    failure_count: int
    relevance_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    items: List[SearchResult]
    total: int
    query: str
    search_type: str  # "keyword" | "semantic" | "hybrid"


# ── Quality Gate Schemas ──────────────────────────────────────

class QualityGateRule(BaseModel):
    rule_type: str  # "pass_rate" | "failure_count" | "new_failures" | "p1_bugs" | "flaky_count"
    threshold: Any
    severity: str = "FAIL"  # "FAIL" | "WARN"
    description: Optional[str] = None


class QualityGateCreate(BaseModel):
    name: str
    rules: List[QualityGateRule]


class QualityGateEvaluationResult(BaseModel):
    gate_id: uuid.UUID
    run_id: uuid.UUID
    status: str  # "PASSED" | "FAILED" | "WARNED"
    rules_evaluated: List[dict]
    evaluated_at: datetime


# ── Notification Schemas ──────────────────────────────────────

class NotificationPreferenceCreate(BaseModel):
    """Create or replace a single channel preference."""
    project_id: Optional[uuid.UUID] = None  # None = all projects
    channel: NotificationChannel
    enabled: bool = True
    events: List[str] = Field(
        default_factory=lambda: ["run_failed", "high_failure_rate"],
        description="List of NotificationEventType values",
    )
    failure_rate_threshold: float = Field(default=80.0, ge=0.0, le=100.0)
    email_override: Optional[EmailStr] = None
    slack_webhook_url: Optional[str] = Field(None, max_length=2000)
    teams_webhook_url: Optional[str] = Field(None, max_length=2000)


class NotificationPreferenceResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    project_id: Optional[uuid.UUID]
    channel: str
    enabled: bool
    events: List[str]
    failure_rate_threshold: Optional[float]
    email_override: Optional[str]
    slack_webhook_url: Optional[str]
    teams_webhook_url: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class NotificationLogResponse(BaseModel):
    id: uuid.UUID
    channel: str
    event_type: str
    title: str
    body: str
    status: str
    is_read: bool
    sent_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestNotificationRequest(BaseModel):
    channel: NotificationChannel
    preference_id: Optional[uuid.UUID] = None


# ── Agent Pipeline Schemas ─────────────────────────────────────

class TriggerPipelineRequest(BaseModel):
    test_run_id: uuid.UUID


class AgentStageResultResponse(BaseModel):
    stage_name: str
    status: str
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None
    result_data: Optional[Any] = None
    error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AgentPipelineResponse(BaseModel):
    id: uuid.UUID
    test_run_id: uuid.UUID
    workflow_type: str
    status: str
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None
    error: Optional[str] = None
    created_at: Any

    model_config = ConfigDict(from_attributes=True)


# ── Chat Schemas ───────────────────────────────────────────────

class ChatSessionCreate(BaseModel):
    project_id: Optional[uuid.UUID] = None
    title: Optional[str] = None


class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    title: Optional[str] = None
    created_at: Any
    updated_at: Any

    model_config = ConfigDict(from_attributes=True)


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    sources: Optional[List[Any]] = None
    created_at: Any

    model_config = ConfigDict(from_attributes=True)


class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    project_id: Optional[str] = None


class SendMessageResponse(BaseModel):
    session_id: uuid.UUID
    reply: str
    sources: List[Any] = []


# ── Test Case Management Schemas ──────────────────────────────────────────────

class TestCaseStepSchema(BaseModel):
    step_number: int
    action: str
    expected_result: str


class ManagedTestCaseCreate(BaseModel):
    project_id: uuid.UUID
    title: str = Field(..., min_length=3, max_length=500)
    description: Optional[str] = None
    objective: Optional[str] = None
    preconditions: Optional[str] = None
    steps: Optional[List[dict]] = None
    expected_result: Optional[str] = None
    test_data: Optional[str] = None
    test_type: str = "functional"
    priority: str = "medium"
    severity: str = "major"
    feature_area: Optional[str] = None
    tags: Optional[List[str]] = None
    estimated_duration_minutes: Optional[int] = None
    is_automated: bool = False
    automation_status: str = "not_automated"


class ManagedTestCaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=500)
    description: Optional[str] = None
    objective: Optional[str] = None
    preconditions: Optional[str] = None
    steps: Optional[List[dict]] = None
    expected_result: Optional[str] = None
    test_data: Optional[str] = None
    test_type: Optional[str] = None
    priority: Optional[str] = None
    severity: Optional[str] = None
    feature_area: Optional[str] = None
    tags: Optional[List[str]] = None
    estimated_duration_minutes: Optional[int] = None
    is_automated: Optional[bool] = None
    automation_status: Optional[str] = None
    change_summary: Optional[str] = None


class ManagedTestCaseResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: Optional[str] = None
    objective: Optional[str] = None
    preconditions: Optional[str] = None
    steps: Optional[List[dict]] = None
    expected_result: Optional[str] = None
    test_data: Optional[str] = None
    test_type: str
    priority: str
    severity: str
    feature_area: Optional[str] = None
    tags: Optional[List[Any]] = None
    status: str
    version: int
    author_id: Optional[uuid.UUID] = None
    assignee_id: Optional[uuid.UUID] = None
    reviewer_id: Optional[uuid.UUID] = None
    is_automated: bool
    automation_status: str
    test_fingerprint: Optional[str] = None
    ai_generated: bool
    ai_quality_score: Optional[int] = None
    ai_review_notes: Optional[dict] = None
    estimated_duration_minutes: Optional[int] = None
    last_executed_at: Optional[datetime] = None
    last_execution_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ManagedTestCaseListResponse(BaseModel):
    items: List[ManagedTestCaseResponse]
    total: int
    page: int
    size: int
    pages: int


class TestCaseVersionResponse(BaseModel):
    id: uuid.UUID
    test_case_id: uuid.UUID
    version: int
    title: str
    description: Optional[str] = None
    steps: Optional[List[dict]] = None
    expected_result: Optional[str] = None
    status: str
    changed_by_id: Optional[uuid.UUID] = None
    change_summary: Optional[str] = None
    change_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestCaseReviewResponse(BaseModel):
    id: uuid.UUID
    test_case_id: uuid.UUID
    reviewer_id: Optional[uuid.UUID] = None
    requested_by_id: Optional[uuid.UUID] = None
    status: str
    ai_review_completed: bool
    ai_quality_score: Optional[int] = None
    ai_review_notes: Optional[dict] = None
    ai_reviewed_at: Optional[datetime] = None
    human_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewActionRequest(BaseModel):
    action: str  # approve|reject|request_changes
    notes: Optional[str] = None


class TestCaseCommentCreate(BaseModel):
    content: str = Field(..., min_length=1)
    comment_type: str = "general"
    parent_id: Optional[uuid.UUID] = None
    step_number: Optional[int] = None


class TestCaseCommentResponse(BaseModel):
    id: uuid.UUID
    test_case_id: uuid.UUID
    author_id: Optional[uuid.UUID] = None
    content: str
    comment_type: str
    parent_id: Optional[uuid.UUID] = None
    step_number: Optional[int] = None
    is_resolved: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestPlanCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(..., min_length=3, max_length=500)
    description: Optional[str] = None
    objective: Optional[str] = None
    planned_start_date: Optional[datetime] = None
    planned_end_date: Optional[datetime] = None
    assigned_to_id: Optional[uuid.UUID] = None


class TestPlanUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=500)
    description: Optional[str] = None
    objective: Optional[str] = None
    status: Optional[str] = None
    planned_start_date: Optional[datetime] = None
    planned_end_date: Optional[datetime] = None
    actual_start_date: Optional[datetime] = None
    actual_end_date: Optional[datetime] = None
    assigned_to_id: Optional[uuid.UUID] = None


class TestPlanResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: Optional[str] = None
    objective: Optional[str] = None
    status: str
    planned_start_date: Optional[datetime] = None
    planned_end_date: Optional[datetime] = None
    actual_start_date: Optional[datetime] = None
    actual_end_date: Optional[datetime] = None
    created_by_id: Optional[uuid.UUID] = None
    assigned_to_id: Optional[uuid.UUID] = None
    ai_generated: bool
    total_cases: int
    executed_cases: int
    passed_cases: int
    failed_cases: int
    blocked_cases: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestPlanListResponse(BaseModel):
    items: List[TestPlanResponse]
    total: int
    page: int
    size: int
    pages: int


class TestPlanItemCreate(BaseModel):
    test_case_id: uuid.UUID
    order_index: int = 0
    priority_override: Optional[str] = None


class TestPlanItemResponse(BaseModel):
    id: uuid.UUID
    plan_id: uuid.UUID
    test_case_id: uuid.UUID
    order_index: int
    priority_override: Optional[str] = None
    execution_status: str
    executed_by_id: Optional[uuid.UUID] = None
    executed_at: Optional[datetime] = None
    execution_notes: Optional[str] = None
    actual_duration_minutes: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExecuteTestPlanItemRequest(BaseModel):
    execution_status: str  # passed|failed|blocked|skipped
    execution_notes: Optional[str] = None
    actual_duration_minutes: Optional[int] = None


class TestStrategyCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(..., min_length=3, max_length=500)
    version_label: str = "v1.0"
    objective: Optional[str] = None
    scope: Optional[str] = None
    test_approach: Optional[str] = None


class TestStrategyUpdate(BaseModel):
    name: Optional[str] = None
    version_label: Optional[str] = None
    status: Optional[str] = None
    objective: Optional[str] = None
    scope: Optional[str] = None
    out_of_scope: Optional[str] = None
    test_approach: Optional[str] = None
    risk_assessment: Optional[List[dict]] = None
    test_types: Optional[List[dict]] = None
    entry_criteria: Optional[List[str]] = None
    exit_criteria: Optional[List[str]] = None
    environments: Optional[List[dict]] = None
    automation_approach: Optional[str] = None
    defect_management: Optional[str] = None


class TestStrategyResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    version_label: str
    status: str
    objective: Optional[str] = None
    scope: Optional[str] = None
    out_of_scope: Optional[str] = None
    test_approach: Optional[str] = None
    risk_assessment: Optional[List[Any]] = None
    test_types: Optional[List[Any]] = None
    entry_criteria: Optional[List[Any]] = None
    exit_criteria: Optional[List[Any]] = None
    environments: Optional[List[Any]] = None
    automation_approach: Optional[str] = None
    defect_management: Optional[str] = None
    ai_generated: bool
    ai_model_used: Optional[str] = None
    created_by_id: Optional[uuid.UUID] = None
    approved_by_id: Optional[uuid.UUID] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    action: str
    actor_id: Optional[uuid.UUID] = None
    actor_name: Optional[str] = None
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    details: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    size: int
    pages: int


class AIGenerateTestCasesRequest(BaseModel):
    project_id: uuid.UUID
    requirements: str = Field(..., min_length=3)
    persist: bool = False  # if True, save generated cases as DRAFT


class AIGenerateTestCasesResponse(BaseModel):
    test_cases: List[dict]
    coverage_summary: Optional[str] = None
    gaps_noted: List[str] = []
    created_ids: List[str] = []


class AIReviewTestCaseResponse(BaseModel):
    quality_score: Optional[int] = None
    grade: Optional[str] = None
    summary: Optional[str] = None
    score_breakdown: Optional[dict] = None
    issues: Optional[List[dict]] = None
    suggestions: Optional[List[dict]] = None
    best_practices_violations: Optional[List[str]] = None
    coverage_gaps: Optional[List[str]] = None
    positive_aspects: Optional[List[str]] = None
    error: Optional[str] = None


class AICoverageAnalysisRequest(BaseModel):
    project_id: uuid.UUID
    requirements: str = Field(..., min_length=3)


class AICoverageAnalysisResponse(BaseModel):
    coverage_score: Optional[int] = None
    covered_areas: Optional[List[str]] = None
    partial_coverage: Optional[List[dict]] = None
    uncovered_areas: Optional[List[str]] = None
    recommended_new_tests: Optional[List[dict]] = None
    risk_assessment: Optional[str] = None
    summary: Optional[str] = None
    error: Optional[str] = None


class AIGenerateStrategyRequest(BaseModel):
    project_id: uuid.UUID
    project_context: str = Field(..., min_length=3)
    strategy_name: Optional[str] = None


class AIOptimizePlanRequest(BaseModel):
    project_id: uuid.UUID
    plan_name: Optional[str] = None
    constraints: Optional[str] = None


class AIOptimizePlanResponse(BaseModel):
    optimized_order: Optional[List[dict]] = None
    execution_phases: Optional[List[dict]] = None
    total_estimated_duration_minutes: Optional[int] = None
    parallel_execution_possible: Optional[bool] = None
    parallel_groups: Optional[List[Any]] = None
    risk_areas_first: Optional[bool] = None
    optimization_notes: Optional[str] = None
    error: Optional[str] = None


class AITaskEnqueueResponse(BaseModel):
    task_id: str
    status: str = "queued"


class AITaskStatusResponse(BaseModel):
    task_id: str
    status: str  # pending | success | failure
    result: Optional[dict] = None
    error: Optional[str] = None


# ── Live Stream Schemas ───────────────────────────────────────────────────────

class LiveSessionCreate(BaseModel):
    """Request body to register a new live execution session."""
    project_id: uuid.UUID
    run_id: Optional[str] = None           # auto-generated if omitted
    client_name: str = Field(..., min_length=1, max_length=255)
    machine_id: Optional[str] = Field(None, max_length=255)
    build_number: Optional[str] = Field(None, max_length=100)
    framework: Optional[str] = Field(None, max_length=50)  # pytest|junit|testng|mocha|…
    branch: Optional[str] = Field(None, max_length=255)
    commit_hash: Optional[str] = Field(None, max_length=64)
    total_tests: Optional[int] = Field(None, ge=0)
    metadata: Optional[dict] = None
    # Optional: name of the release this execution belongs to.
    # Auto-created in "planning" status if it does not exist in the project.
    release_name: Optional[str] = Field(None, max_length=255)


class LiveSessionResponse(BaseModel):
    """Response returned when a session is created."""
    session_id: str
    session_token: str    # plaintext token — client stores this for X-Session-Token header
    run_id: str
    project_id: str
    expires_in: int       # seconds until token expires
    created_at: datetime


class LiveEvent(BaseModel):
    """A single test execution event from a client machine."""
    event_type: str = Field(
        ...,
        description="run_start | test_start | test_result | log | metric | run_complete",
    )
    test_name: Optional[str] = Field(None, max_length=1000)
    status: Optional[str] = Field(None, description="PASSED | FAILED | SKIPPED | BROKEN")
    duration_ms: Optional[int] = Field(None, ge=0)
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    suite_name: Optional[str] = Field(None, max_length=500)
    class_name: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = None
    # Client-side unix epoch ms — preserved for ordering; falls back to server time if absent
    timestamp_ms: Optional[int] = None
    metadata: Optional[dict] = None


class LiveEventBatch(BaseModel):
    """
    A batch of events sent from a client machine.
    Batching amortises HTTP overhead — 50–1000 events per call is recommended.
    """
    session_id: str
    run_id: str
    events: List[LiveEvent] = Field(..., min_length=1, max_length=1000)


class LiveEventBatchResponse(BaseModel):
    accepted: int
    run_id: str
    session_id: str


class LiveSessionState(BaseModel):
    """Live state of an active or recently completed session."""
    run_id: str
    project_id: str
    build_number: str
    status: str
    total: int
    passed: int
    failed: int
    skipped: int
    broken: int
    pass_rate: float
    current_test: Optional[str] = None
    started_at: Optional[str] = None
    last_event_at: Optional[str] = None
    client_name: Optional[str] = None
    completed_at: Optional[str] = None
    release_name: Optional[str] = None


class ActiveSessionsResponse(BaseModel):
    sessions: List[LiveSessionState]
    count: int


# ── SMTP / App Settings Schemas ────────────────────────────────

class SmtpConfigRead(BaseModel):
    """SMTP server configuration returned to the client (no password)."""
    enabled: bool
    host: str
    port: int
    user: Optional[str]
    from_address: str
    implicit_tls: bool = Field(
        description=(
            "When True, implicit TLS (SSL/TLS on connect, typically port 465) is used. "
            "When False, STARTTLS (upgrade after connect, typically port 587) is used. "
            "Plain (unencrypted) SMTP is not supported."
        )
    )
    password_set: bool  # True if a password is stored; never returns the value


class SmtpConfigUpdate(BaseModel):
    """Payload for updating SMTP server configuration."""
    enabled: bool = False
    host: str = Field(default="localhost", max_length=255)
    port: int = Field(default=587, ge=1, le=65535)
    user: Optional[str] = Field(default=None, max_length=255)
    password: Optional[str] = Field(default=None, max_length=1000)  # None = keep existing
    from_address: str = Field(default="noreply@qainsight.io", max_length=255)
    implicit_tls: bool = Field(
        default=True,
        description=(
            "When True, implicit TLS (SSL/TLS on connect, typically port 465) is used. "
            "When False, STARTTLS (upgrade after connect, typically port 587) is used. "
            "Plain (unencrypted) SMTP is not supported."
        ),
    )


class SmtpTestResult(BaseModel):
    success: bool
    message: str


# ── User Management Schemas ───────────────────────────────────

class UserListResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UpdateUserRoleRequest(BaseModel):
    role: UserRole


class UpdateUserStatusRequest(BaseModel):
    is_active: bool


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.QA_ENGINEER


class InviteUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole
    expires_at: datetime
    invitation_link: str  # frontend URL with token
    model_config = ConfigDict(from_attributes=True)


# ── Project Member Schemas ────────────────────────────────────

class ProjectMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID
    role: UserRole
    created_at: datetime
    # Joined user fields
    email: str
    username: str
    full_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class AddProjectMemberRequest(BaseModel):
    user_id: uuid.UUID
    role: UserRole = UserRole.QA_ENGINEER


class UpdateProjectMemberRoleRequest(BaseModel):
    role: UserRole


# ── API Key Schemas ───────────────────────────────────────────

class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    scopes: List[str] = Field(default_factory=list)
    expires_days: Optional[int] = Field(None, ge=1, le=365)


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_hint: str
    scopes: List[str]
    is_active: bool
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Returned ONCE at creation — includes the plaintext key."""
    raw_key: str
