"""Pydantic v2 request/response schemas for all API endpoints."""
import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.postgres import FailureCategory, LaunchStatus, Severity, TestStatus, UserRole


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

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    username: str
    password: str


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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
