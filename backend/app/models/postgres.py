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
