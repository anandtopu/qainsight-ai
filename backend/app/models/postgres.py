"""SQLAlchemy ORM models — all PostgreSQL tables."""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


# ── Enums ────────────────────────────────────────────────────

class TestStatus(str, PyEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BROKEN = "BROKEN"
    UNKNOWN = "UNKNOWN"


class LaunchStatus(str, PyEnum):
    IN_PROGRESS = "IN_PROGRESS"
    PASSED = "PASSED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class FailureCategory(str, PyEnum):
    PRODUCT_BUG = "PRODUCT_BUG"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    TEST_DATA = "TEST_DATA"
    AUTOMATION_DEFECT = "AUTOMATION_DEFECT"
    FLAKY = "FLAKY"
    UNKNOWN = "UNKNOWN"


class Severity(str, PyEnum):
    BLOCKER = "BLOCKER"
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    TRIVIAL = "TRIVIAL"


class UserRole(str, PyEnum):
    VIEWER = "VIEWER"
    TESTER = "TESTER"
    QA_ENGINEER = "QA_ENGINEER"
    QA_LEAD = "QA_LEAD"
    ADMIN = "ADMIN"


class NotificationChannel(str, PyEnum):
    EMAIL = "email"
    SLACK = "slack"
    TEAMS = "teams"


class NotificationEventType(str, PyEnum):
    RUN_FAILED = "run_failed"
    RUN_PASSED = "run_passed"
    HIGH_FAILURE_RATE = "high_failure_rate"
    AI_ANALYSIS_COMPLETE = "ai_analysis_complete"
    QUALITY_GATE_FAILED = "quality_gate_failed"
    FLAKY_TEST_DETECTED = "flaky_test_detected"


# ── Models ───────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(String(20), default=UserRole.QA_ENGINEER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    jira_project_key: Mapped[Optional[str]] = mapped_column(String(50))
    splunk_index: Mapped[Optional[str]] = mapped_column(String(255))
    ocp_namespace: Mapped[Optional[str]] = mapped_column(String(255))
    jenkins_job_pattern: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationships
    test_runs: Mapped[list["TestRun"]] = relationship("TestRun", back_populates="project", lazy="dynamic")
    quality_gates: Mapped[list["QualityGate"]] = relationship("QualityGate", back_populates="project")


class TestRun(Base):
    """Represents a single CI/CD pipeline execution (Jenkins build)."""
    __tablename__ = "test_runs"
    __table_args__ = (
        UniqueConstraint("project_id", "build_number", "jenkins_job", name="uq_test_run_build"),
        Index("ix_test_runs_project_status", "project_id", "status"),
        Index("ix_test_runs_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    build_number: Mapped[str] = mapped_column(String(100), nullable=False)
    jenkins_job: Mapped[Optional[str]] = mapped_column(String(500))
    trigger_source: Mapped[Optional[str]] = mapped_column(String(50))  # push | schedule | manual
    branch: Mapped[Optional[str]] = mapped_column(String(255))
    commit_hash: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[LaunchStatus] = mapped_column(String(20), default=LaunchStatus.IN_PROGRESS)

    # Aggregated counts
    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    passed_tests: Mapped[int] = mapped_column(Integer, default=0)
    failed_tests: Mapped[int] = mapped_column(Integer, default=0)
    skipped_tests: Mapped[int] = mapped_column(Integer, default=0)
    broken_tests: Mapped[int] = mapped_column(Integer, default=0)
    pass_rate: Mapped[Optional[float]] = mapped_column(Float)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # OpenShift metadata
    ocp_pod_name: Mapped[Optional[str]] = mapped_column(String(255))
    ocp_node: Mapped[Optional[str]] = mapped_column(String(255))
    ocp_namespace: Mapped[Optional[str]] = mapped_column(String(255))
    ocp_metadata: Mapped[Optional[dict]] = mapped_column(JSON)

    # S3 references
    minio_prefix: Mapped[Optional[str]] = mapped_column(String(1000))

    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="test_runs")
    test_cases: Mapped[list["TestCase"]] = relationship("TestCase", back_populates="test_run", lazy="dynamic")


class TestCase(Base):
    """Individual test case result within a run."""
    __tablename__ = "test_cases"
    __table_args__ = (
        Index("ix_test_cases_run_status", "test_run_id", "status"),
        Index("ix_test_cases_fingerprint", "test_fingerprint"),
        Index("ix_test_cases_search", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False)
    test_fingerprint: Mapped[str] = mapped_column(String(64), index=True)  # hash(test_name + class_name)

    # Core fields from Allure/TestNG
    test_name: Mapped[str] = mapped_column(String(1000), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(2000))
    suite_name: Mapped[Optional[str]] = mapped_column(String(500))
    class_name: Mapped[Optional[str]] = mapped_column(String(500))
    package_name: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[TestStatus] = mapped_column(String(20), nullable=False, default=TestStatus.UNKNOWN)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Allure labels
    severity: Mapped[Optional[Severity]] = mapped_column(String(20))
    feature: Mapped[Optional[str]] = mapped_column(String(500))
    story: Mapped[Optional[str]] = mapped_column(String(500))
    epic: Mapped[Optional[str]] = mapped_column(String(500))
    owner: Mapped[Optional[str]] = mapped_column(String(255))
    tags: Mapped[Optional[list]] = mapped_column(JSON)

    # Failure info
    failure_category: Mapped[Optional[FailureCategory]] = mapped_column(String(30))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # S3 reference
    minio_s3_prefix: Mapped[Optional[str]] = mapped_column(String(1000))
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False)

    # Full-text search vector
    search_vector: Mapped[Optional[Any]] = mapped_column(TSVECTOR)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationships
    test_run: Mapped["TestRun"] = relationship("TestRun", back_populates="test_cases")
    history: Mapped[list["TestCaseHistory"]] = relationship("TestCaseHistory", back_populates="test_case")
    ai_analysis: Mapped[Optional["AIAnalysis"]] = relationship("AIAnalysis", back_populates="test_case", uselist=False)
    defects: Mapped[list["Defect"]] = relationship("Defect", back_populates="test_case")


class TestCaseHistory(Base):
    """Denormalized history for fast timeline queries."""
    __tablename__ = "test_case_history"
    __table_args__ = (
        Index("ix_history_fingerprint_date", "test_fingerprint", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"))
    test_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"))
    test_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[TestStatus] = mapped_column(String(20), nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    failure_category: Mapped[Optional[FailureCategory]] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    test_case: Mapped["TestCase"] = relationship("TestCase", back_populates="history")


class AIAnalysis(Base):
    """Stored AI triage results per test case."""
    __tablename__ = "ai_analysis"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), unique=True)
    root_cause_summary: Mapped[Optional[str]] = mapped_column(Text)
    failure_category: Mapped[Optional[FailureCategory]] = mapped_column(String(30))
    backend_error_found: Mapped[bool] = mapped_column(Boolean, default=False)
    pod_issue_found: Mapped[bool] = mapped_column(Boolean, default=False)
    is_flaky: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence_score: Mapped[Optional[int]] = mapped_column(Integer)
    recommended_actions: Mapped[Optional[list]] = mapped_column(JSON)
    evidence_references: Mapped[Optional[list]] = mapped_column(JSON)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(50))
    llm_model: Mapped[Optional[str]] = mapped_column(String(100))
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    test_case: Mapped["TestCase"] = relationship("TestCase", back_populates="ai_analysis")


class Defect(Base):
    """Defect records linked to test cases."""
    __tablename__ = "defects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    jira_ticket_id: Mapped[Optional[str]] = mapped_column(String(50))
    jira_ticket_url: Mapped[Optional[str]] = mapped_column(String(1000))
    jira_status: Mapped[Optional[str]] = mapped_column(String(50))
    ai_confidence_score: Mapped[Optional[int]] = mapped_column(Integer)
    failure_category: Mapped[Optional[FailureCategory]] = mapped_column(String(30))
    resolution_status: Mapped[str] = mapped_column(String(50), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    test_case: Mapped["TestCase"] = relationship("TestCase", back_populates="defects")


class QualityGate(Base):
    """Quality gate rule configuration per project."""
    __tablename__ = "quality_gates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rules: Mapped[list] = mapped_column(JSON, default=list)  # List of rule objects
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="quality_gates")


class CoverageSnapshot(Base):
    """Daily test coverage snapshots for trend charts."""
    __tablename__ = "coverage_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    snapshot_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    total_suites: Mapped[int] = mapped_column(Integer, default=0)
    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    automated_count: Mapped[int] = mapped_column(Integer, default=0)
    suite_coverage: Mapped[Optional[dict]] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("project_id", "snapshot_date", name="uq_coverage_project_date"),
    )


class NotificationPreference(Base):
    """Per-user, per-channel notification configuration."""
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", "channel", name="uq_notif_pref"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # NULL project_id = applies to all projects
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    channel: Mapped[NotificationChannel] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # JSON list of NotificationEventType values the user subscribed to
    events: Mapped[list] = mapped_column(JSON, default=list)
    # Alert only when pass_rate falls below this percentage
    failure_rate_threshold: Mapped[Optional[float]] = mapped_column(Float, default=80.0)
    # Channel-specific overrides (if None, falls back to global settings)
    email_override: Mapped[Optional[str]] = mapped_column(String(255))
    slack_webhook_url: Mapped[Optional[str]] = mapped_column(String(2000))
    teams_webhook_url: Mapped[Optional[str]] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class AgentPipelineRun(Base):
    """Tracks a single execution of the multi-agent pipeline for a test run."""
    __tablename__ = "agent_pipeline_runs"
    __table_args__ = (
        Index("ix_pipeline_runs_test_run", "test_run_id"),
        Index("ix_pipeline_runs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(20), default="offline")  # offline | live
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|completed|failed|partial
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    stages: Mapped[list["AgentStageResult"]] = relationship("AgentStageResult", back_populates="pipeline_run", cascade="all, delete-orphan")


class AgentStageResult(Base):
    """Per-stage result for an AgentPipelineRun."""
    __tablename__ = "agent_stage_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_pipeline_runs.id", ondelete="CASCADE"), nullable=False)
    stage_name: Mapped[str] = mapped_column(String(50), nullable=False)  # ingestion|anomaly|analysis|summary|triage
    status: Mapped[str] = mapped_column(String(20), default="pending")   # pending|running|completed|failed|skipped
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    result_data: Mapped[Optional[dict]] = mapped_column(JSON)
    error: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    pipeline_run: Mapped["AgentPipelineRun"] = relationship("AgentPipelineRun", back_populates="stages")


class ChatSession(Base):
    """A conversation session between a user and the Conversation Agent."""
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationships
    messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """A single message in a ChatSession."""
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_session", "session_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[Optional[list]] = mapped_column(JSON)  # [{type, id, label}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")


class FeedbackRating(str, PyEnum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIALLY_CORRECT = "partially_correct"


class AIFeedback(Base):
    """
    Human feedback on AI triage results — the primary training signal.

    Sources:
      - manual: engineer rates analysis card in the UI (explicit)
      - jira_resolved: Jira ticket created by AI was resolved (implicit positive)
      - jira_invalid: Jira ticket closed as invalid/won't-fix (implicit negative)
      - category_correction: engineer changed the failure_category in the UI
    """
    __tablename__ = "ai_feedback"
    __table_args__ = (
        Index("ix_ai_feedback_analysis", "analysis_id"),
        Index("ix_ai_feedback_created", "created_at"),
        Index("ix_ai_feedback_rating", "rating"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_analysis.id", ondelete="CASCADE"), nullable=False)
    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rating: Mapped[FeedbackRating] = mapped_column(String(25), nullable=False)
    corrected_category: Mapped[Optional[FailureCategory]] = mapped_column(String(30), nullable=True)
    corrected_root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # "manual" | "jira_resolved" | "jira_invalid" | "category_correction"
    source: Mapped[str] = mapped_column(String(50), default="manual")
    # Whether this record has been exported into a training batch
    exported: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ModelVersion(Base):
    """
    Registry of fine-tuned model versions per training track.

    Tracks the full lifecycle: training → evaluation → active/retired.
    The model_registry service uses this table + Redis for hot-swap lookups.
    """
    __tablename__ = "model_versions"
    __table_args__ = (
        Index("ix_model_versions_track_status", "track", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Track: "classifier" | "reasoning" | "embedding"
    track: Mapped[str] = mapped_column(String(30), nullable=False)
    # Human-readable model name (e.g. "qwen2.5:7b-qainsight-v3", "ft:gpt-4o-mini:qainsight-2025-07")
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    # Status: "training" | "evaluating" | "active" | "retired" | "failed"
    status: Mapped[str] = mapped_column(String(20), default="training")
    # Training metadata
    training_examples: Mapped[int] = mapped_column(Integer, default=0)
    holdout_examples: Mapped[int] = mapped_column(Integer, default=0)
    # Evaluation metrics
    eval_accuracy: Mapped[Optional[float]] = mapped_column(Float)
    baseline_accuracy: Mapped[Optional[float]] = mapped_column(Float)
    eval_details: Mapped[Optional[dict]] = mapped_column(JSON)
    # Provider-specific job ID (OpenAI fine-tuning job ID, Ollama model tag, etc.)
    provider_job_id: Mapped[Optional[str]] = mapped_column(String(200))
    # Path to JSONL training file in MinIO
    training_file_path: Mapped[Optional[str]] = mapped_column(String(1000))
    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class FailureCluster(Base):
    """Semantic cluster of failures grouped by root-cause similarity."""
    __tablename__ = "failure_clusters"
    __table_args__ = (
        Index("ix_failure_clusters_run", "test_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False)
    pipeline_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("agent_pipeline_runs.id", ondelete="SET NULL"), nullable=True)
    cluster_id: Mapped[str] = mapped_column(String(20), nullable=False)           # e.g. "cl_001"
    label: Mapped[str] = mapped_column(String(500), nullable=False)               # short human-readable label
    representative_error: Mapped[Optional[str]] = mapped_column(Text)
    member_test_ids: Mapped[list] = mapped_column(JSON, default=list)             # list[str] UUIDs
    size: Mapped[int] = mapped_column(Integer, default=1)
    cohesion_score: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeepFinding(Base):
    """Deep investigation result per failure cluster."""
    __tablename__ = "deep_findings"
    __table_args__ = (
        Index("ix_deep_findings_run", "test_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False)
    cluster_id: Mapped[str] = mapped_column(String(20), nullable=False)
    root_cause: Mapped[Optional[str]] = mapped_column(Text)
    failure_category: Mapped[Optional[FailureCategory]] = mapped_column(String(30))
    confidence_score: Mapped[Optional[int]] = mapped_column(Integer)
    causal_chain: Mapped[Optional[list]] = mapped_column(JSON)                    # list[{step, service, finding}]
    evidence: Mapped[Optional[list]] = mapped_column(JSON)                        # list[{source, excerpt}]
    affected_services: Mapped[Optional[list]] = mapped_column(JSON)               # list[str]
    contract_violations: Mapped[Optional[list]] = mapped_column(JSON)             # list[ContractViolation dicts]
    log_evidence: Mapped[Optional[dict]] = mapped_column(JSON)
    recommended_actions: Mapped[Optional[list]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReleaseDecision(Base):
    """Release gate decision produced by ReleaseRiskAgent."""
    __tablename__ = "release_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, unique=True)
    recommendation: Mapped[str] = mapped_column(String(20), nullable=False)       # GO | NO_GO | CONDITIONAL_GO
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=50)  # 0-100
    blocking_issues: Mapped[Optional[list]] = mapped_column(JSON)
    conditions_for_go: Mapped[Optional[list]] = mapped_column(JSON)
    reasoning: Mapped[Optional[str]] = mapped_column(Text)
    human_override: Mapped[Optional[str]] = mapped_column(Text)                   # QA lead override reason
    overridden_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class ContractViolation(Base):
    """API contract violation detected by ContractAgent."""
    __tablename__ = "contract_violations"
    __table_args__ = (
        Index("ix_contract_violations_run", "test_run_id"),
        Index("ix_contract_violations_tc", "test_case_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False)
    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    endpoint: Mapped[Optional[str]] = mapped_column(String(500))
    violation_type: Mapped[str] = mapped_column(String(50), nullable=False)       # missing_field|type_mismatch|schema_drift|constraint_violation
    field_path: Mapped[Optional[str]] = mapped_column(String(500))
    expected: Mapped[Optional[str]] = mapped_column(String(500))
    actual: Mapped[Optional[str]] = mapped_column(String(500))
    severity: Mapped[str] = mapped_column(String(20), default="warning")          # critical|warning|info
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationLog(Base):
    """Audit trail for every dispatched notification."""
    __tablename__ = "notification_logs"
    __table_args__ = (
        Index("ix_notif_log_user_created", "user_id", "created_at"),
        Index("ix_notif_log_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | sent | failed
    error_detail: Mapped[Optional[str]] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
