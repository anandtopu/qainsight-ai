"""Test Case Management — full lifecycle CRUD, review workflow, AI generation, test plans, test strategy."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.core.deps import get_current_active_user
from app.models.postgres import (
    ManagedTestCase, TestCaseVersion, TestCaseReview, TestCaseComment,
    TestPlan, TestPlanItem, TestStrategy, TestCaseAuditLog, User
)
from app.models.schemas import (
    ManagedTestCaseCreate, ManagedTestCaseUpdate, ManagedTestCaseResponse,
    ManagedTestCaseListResponse, TestCaseVersionResponse,
    TestCaseReviewResponse, TestCaseCommentCreate, TestCaseCommentResponse,
    TestPlanCreate, TestPlanUpdate, TestPlanResponse, TestPlanListResponse,
    TestPlanItemCreate, TestPlanItemResponse, ExecuteTestPlanItemRequest,
    TestStrategyUpdate, TestStrategyResponse,
    AuditLogResponse, AuditLogListResponse,
    AIGenerateTestCasesRequest, AIGenerateTestCasesResponse,
    AIReviewTestCaseResponse, AICoverageAnalysisRequest, AICoverageAnalysisResponse,
    AIGenerateStrategyRequest, AIOptimizePlanRequest,
    ReviewActionRequest,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/test-management", tags=["Test Management"])


# ── Audit helper ──────────────────────────────────────────────────────────────

async def _audit(
    db: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
    project_id: Optional[uuid.UUID],
    action: str,
    actor: User,
    old_values: Optional[dict] = None,
    new_values: Optional[dict] = None,
    details: Optional[str] = None,
) -> None:
    log = TestCaseAuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        project_id=project_id,
        action=action,
        actor_id=actor.id,
        actor_name=actor.full_name or actor.username,
        old_values=old_values,
        new_values=new_values,
        details=details,
    )
    db.add(log)


def _row(model_instance, schema_class):
    """Map ORM instance to Pydantic schema using from_attributes."""
    return schema_class.model_validate(model_instance)


# ── Test Cases ────────────────────────────────────────────────────────────────

@router.get("/cases", response_model=ManagedTestCaseListResponse)
async def list_test_cases(
    project_id: uuid.UUID,
    status: Optional[str] = None,
    test_type: Optional[str] = None,
    priority: Optional[str] = None,
    feature_area: Optional[str] = None,
    ai_generated: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List managed test cases for a project with optional filters.
    Deprecated (soft-deleted) cases are hidden by default unless status=deprecated is requested.
    """
    q = select(ManagedTestCase).where(ManagedTestCase.project_id == project_id)
    if status:
        q = q.where(ManagedTestCase.status == status)
    else:
        # Exclude soft-deleted cases from the default view
        q = q.where(ManagedTestCase.status != "deprecated")
    if test_type:
        q = q.where(ManagedTestCase.test_type == test_type)
    if priority:
        q = q.where(ManagedTestCase.priority == priority)
    if feature_area:
        q = q.where(ManagedTestCase.feature_area == feature_area)
    if ai_generated is not None:
        q = q.where(ManagedTestCase.ai_generated == ai_generated)
    if search:
        q = q.where(ManagedTestCase.title.ilike(f"%{search}%"))

    count_q = select(func.count()).select_from(q.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    q = q.order_by(ManagedTestCase.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    items = result.scalars().all()

    return {
        "items": [_row(i, ManagedTestCaseResponse) for i in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": -(-total // size),
    }


@router.post("/cases", response_model=ManagedTestCaseResponse, status_code=status.HTTP_201_CREATED)
async def create_test_case(
    payload: ManagedTestCaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new managed test case (starts in DRAFT)."""
    tc = ManagedTestCase(
        **payload.model_dump(exclude_unset=True, exclude={"change_summary"}),
        author_id=current_user.id,
        status="draft",
        version=1,
    )
    db.add(tc)
    await db.flush()

    # Create initial version snapshot
    ver = TestCaseVersion(
        test_case_id=tc.id,
        version=1,
        title=tc.title,
        description=tc.description,
        steps=tc.steps,
        expected_result=tc.expected_result,
        status="draft",
        changed_by_id=current_user.id,
        change_summary="Initial creation",
        change_type="created",
    )
    db.add(ver)

    await _audit(db, "test_case", tc.id, tc.project_id, "created", current_user,
                 details=f"Test case '{tc.title}' created")
    await db.commit()
    await db.refresh(tc)
    return _row(tc, ManagedTestCaseResponse)


@router.get("/cases/{case_id}", response_model=ManagedTestCaseResponse)
async def get_test_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.get(ManagedTestCase, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Test case not found")
    return _row(result, ManagedTestCaseResponse)


@router.patch("/cases/{case_id}", response_model=ManagedTestCaseResponse)
async def update_test_case(
    case_id: uuid.UUID,
    payload: ManagedTestCaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a test case and create a new version snapshot."""
    tc = await db.get(ManagedTestCase, case_id)
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    if tc.status in ("deprecated",):
        raise HTTPException(status_code=400, detail="Cannot edit a deprecated test case")

    old = {"title": tc.title, "status": tc.status, "version": tc.version}
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tc, field, value)
    tc.version += 1

    ver = TestCaseVersion(
        test_case_id=tc.id,
        version=tc.version,
        title=tc.title,
        description=tc.description,
        steps=tc.steps,
        expected_result=tc.expected_result,
        status=tc.status,
        changed_by_id=current_user.id,
        change_summary=payload.change_summary or f"Updated to v{tc.version}",
        change_type="updated",
    )
    db.add(ver)

    await _audit(db, "test_case", tc.id, tc.project_id, "updated", current_user,
                 old_values=old, new_values=update_data)
    await db.commit()
    await db.refresh(tc)
    return _row(tc, ManagedTestCaseResponse)


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deprecate_test_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Soft-delete: move test case to DEPRECATED status."""
    tc = await db.get(ManagedTestCase, case_id)
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    old_status = tc.status
    tc.status = "deprecated"
    await _audit(db, "test_case", tc.id, tc.project_id, "deleted", current_user,
                 old_values={"status": old_status}, new_values={"status": "deprecated"})
    await db.commit()


@router.get("/cases/{case_id}/history", response_model=list[TestCaseVersionResponse])
async def get_test_case_history(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get version history for a test case."""
    q = select(TestCaseVersion).where(TestCaseVersion.test_case_id == case_id).order_by(TestCaseVersion.version.desc())
    result = await db.execute(q)
    return [_row(v, TestCaseVersionResponse) for v in result.scalars().all()]


# ── Review Workflow ───────────────────────────────────────────────────────────

@router.post("/cases/{case_id}/request-review", response_model=TestCaseReviewResponse)
async def request_review(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Submit test case for review (DRAFT → REVIEW_REQUESTED)."""
    tc = await db.get(ManagedTestCase, case_id)
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    if tc.status not in ("draft", "rejected"):
        raise HTTPException(status_code=400, detail=f"Cannot request review from status '{tc.status}'")

    tc.status = "review_requested"
    review = TestCaseReview(
        test_case_id=case_id,
        requested_by_id=current_user.id,
        status="pending",
    )
    db.add(review)
    await _audit(db, "test_case", tc.id, tc.project_id, "status_changed", current_user,
                 old_values={"status": "draft"}, new_values={"status": "review_requested"})
    await db.commit()
    await db.refresh(review)
    return _row(review, TestCaseReviewResponse)


@router.post("/cases/{case_id}/review-action", response_model=ManagedTestCaseResponse)
async def review_action(
    case_id: uuid.UUID,
    payload: ReviewActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Approve or reject a test case under review. QA_LEAD or QA_ENGINEER role."""
    from app.models.postgres import UserRole
    if current_user.role not in (UserRole.QA_LEAD, UserRole.ADMIN, UserRole.QA_ENGINEER):
        raise HTTPException(status_code=403, detail="Insufficient permissions to review")

    tc = await db.get(ManagedTestCase, case_id)
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    if tc.status not in ("review_requested", "under_review"):
        raise HTTPException(status_code=400, detail=f"Test case is not under review (status: {tc.status})")

    if payload.action == "approve":
        tc.status = "approved"
        new_review_status = "approved"
    elif payload.action == "reject":
        tc.status = "rejected"
        new_review_status = "rejected"
    elif payload.action == "request_changes":
        tc.status = "draft"
        new_review_status = "changes_requested"
    else:
        raise HTTPException(status_code=400, detail="action must be approve|reject|request_changes")

    # Update latest review record
    review_q = select(TestCaseReview).where(
        TestCaseReview.test_case_id == case_id
    ).order_by(TestCaseReview.created_at.desc()).limit(1)
    review_result = await db.execute(review_q)
    review = review_result.scalars().first()
    if review:
        review.status = new_review_status
        review.reviewer_id = current_user.id
        review.human_notes = payload.notes
        review.reviewed_at = datetime.now(timezone.utc)

    await _audit(db, "test_case", tc.id, tc.project_id, payload.action, current_user,
                 details=payload.notes)
    await db.commit()
    await db.refresh(tc)
    return _row(tc, ManagedTestCaseResponse)


@router.get("/cases/{case_id}/reviews", response_model=list[TestCaseReviewResponse])
async def get_reviews(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(TestCaseReview).where(TestCaseReview.test_case_id == case_id).order_by(TestCaseReview.created_at.desc())
    result = await db.execute(q)
    return [_row(r, TestCaseReviewResponse) for r in result.scalars().all()]


# ── Comments ──────────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/comments", response_model=list[TestCaseCommentResponse])
async def list_comments(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(TestCaseComment).where(TestCaseComment.test_case_id == case_id).order_by(TestCaseComment.created_at.asc())
    result = await db.execute(q)
    return [_row(c, TestCaseCommentResponse) for c in result.scalars().all()]


@router.post("/cases/{case_id}/comments", response_model=TestCaseCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    case_id: uuid.UUID,
    payload: TestCaseCommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    tc = await db.get(ManagedTestCase, case_id)
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    comment = TestCaseComment(
        test_case_id=case_id,
        author_id=current_user.id,
        **payload.model_dump(exclude_unset=True),
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return _row(comment, TestCaseCommentResponse)


# ── AI Endpoints ──────────────────────────────────────────────────────────────

@router.post("/cases/ai-generate", response_model=AIGenerateTestCasesResponse)
async def ai_generate_cases(
    payload: AIGenerateTestCasesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Use AI to generate test cases from a requirements description.
    Optionally persists them as DRAFT test cases."""
    from app.services.test_case_ai_agent import ai_generate_test_cases
    result = await ai_generate_test_cases(payload.requirements)

    created_ids: list[str] = []
    if payload.persist and result.get("test_cases"):
        for tc_data in result["test_cases"]:
            tc = ManagedTestCase(
                project_id=payload.project_id,
                title=tc_data.get("title", "AI Generated Test Case"),
                description=tc_data.get("objective"),
                objective=tc_data.get("objective"),
                preconditions=tc_data.get("preconditions"),
                steps=tc_data.get("steps"),
                expected_result=tc_data.get("expected_result"),
                test_data=tc_data.get("test_data"),
                test_type=tc_data.get("test_type", "functional"),
                priority=tc_data.get("priority", "medium"),
                severity=tc_data.get("severity", "major"),
                feature_area=tc_data.get("feature_area"),
                tags=tc_data.get("tags", []),
                estimated_duration_minutes=tc_data.get("estimated_duration_minutes"),
                ai_generated=True,
                ai_generation_prompt=payload.requirements,
                author_id=current_user.id,
                status="draft",
                version=1,
            )
            db.add(tc)
            await db.flush()
            ver = TestCaseVersion(
                test_case_id=tc.id,
                version=1,
                title=tc.title,
                description=tc.description,
                steps=tc.steps,
                expected_result=tc.expected_result,
                status="draft",
                changed_by_id=current_user.id,
                change_summary="AI generated",
                change_type="created",
            )
            db.add(ver)
            await _audit(db, "test_case", tc.id, payload.project_id, "ai_generated", current_user,
                         details=f"AI generated from requirements: {payload.requirements[:100]}")
            created_ids.append(str(tc.id))
        await db.commit()

    return {
        "test_cases": result.get("test_cases", []),
        "coverage_summary": result.get("coverage_summary"),
        "gaps_noted": result.get("gaps_noted", []),
        "created_ids": created_ids,
    }


@router.post("/cases/{case_id}/ai-review", response_model=AIReviewTestCaseResponse)
async def ai_review_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Trigger AI quality review for a specific test case."""
    from app.services.test_case_ai_agent import ai_review_test_case
    tc = await db.get(ManagedTestCase, case_id)
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")

    tc_dict = {
        "title": tc.title,
        "objective": tc.objective,
        "preconditions": tc.preconditions,
        "steps": tc.steps or [],
        "expected_result": tc.expected_result,
        "test_data": tc.test_data,
        "test_type": tc.test_type,
    }
    result = await ai_review_test_case(tc_dict)

    # Persist AI review notes on the test case
    tc.ai_quality_score = result.get("quality_score")
    tc.ai_review_notes = result

    # Create/update review record with AI notes
    review_q = select(TestCaseReview).where(
        TestCaseReview.test_case_id == case_id,
        TestCaseReview.ai_review_completed == False,  # noqa: E712
    ).limit(1)
    review_result = await db.execute(review_q)
    review = review_result.scalars().first()
    if not review:
        review = TestCaseReview(test_case_id=case_id, requested_by_id=current_user.id, status="in_progress")
        db.add(review)
        await db.flush()
    review.ai_review_completed = True
    review.ai_quality_score = result.get("quality_score")
    review.ai_review_notes = result
    review.ai_reviewed_at = datetime.now(timezone.utc)

    await _audit(db, "test_case", tc.id, tc.project_id, "ai_reviewed", current_user,
                 new_values={"ai_quality_score": result.get("quality_score")})
    await db.commit()
    return result


@router.post("/cases/ai-coverage", response_model=AICoverageAnalysisResponse)
async def ai_coverage_analysis(
    payload: AICoverageAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Analyze coverage gaps between requirements and existing test cases."""
    from app.services.test_case_ai_agent import ai_analyze_coverage
    q = select(ManagedTestCase).where(
        ManagedTestCase.project_id == payload.project_id,
        ManagedTestCase.status.in_(["approved", "active", "draft"]),
    ).limit(200)
    result = await db.execute(q)
    existing = [{"title": tc.title, "objective": tc.objective or ""} for tc in result.scalars().all()]
    return await ai_analyze_coverage(payload.requirements, existing)


# ── Test Plans ────────────────────────────────────────────────────────────────

@router.get("/plans", response_model=TestPlanListResponse)
async def list_plans(
    project_id: uuid.UUID,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(TestPlan).where(TestPlan.project_id == project_id)
    if status:
        q = q.where(TestPlan.status == status)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    q = q.order_by(TestPlan.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    return {
        "items": [_row(p, TestPlanResponse) for p in result.scalars().all()],
        "total": total, "page": page, "size": size, "pages": -(-total // size),
    }


@router.post("/plans", response_model=TestPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: TestPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = TestPlan(**payload.model_dump(exclude_unset=True), created_by_id=current_user.id)
    db.add(plan)
    await db.flush()
    await _audit(db, "test_plan", plan.id, plan.project_id, "created", current_user,
                 details=f"Test plan '{plan.name}' created")
    await db.commit()
    await db.refresh(plan)
    return _row(plan, TestPlanResponse)


@router.get("/plans/{plan_id}", response_model=TestPlanResponse)
async def get_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = await db.get(TestPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Test plan not found")
    return _row(plan, TestPlanResponse)


@router.patch("/plans/{plan_id}", response_model=TestPlanResponse)
async def update_plan(
    plan_id: uuid.UUID,
    payload: TestPlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = await db.get(TestPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Test plan not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await _audit(db, "test_plan", plan.id, plan.project_id, "updated", current_user)
    await db.commit()
    await db.refresh(plan)
    return _row(plan, TestPlanResponse)


@router.get("/plans/{plan_id}/items", response_model=list[TestPlanItemResponse])
async def list_plan_items(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(TestPlanItem).where(TestPlanItem.plan_id == plan_id).order_by(TestPlanItem.order_index)
    result = await db.execute(q)
    return [_row(i, TestPlanItemResponse) for i in result.scalars().all()]


@router.post("/plans/{plan_id}/items", response_model=TestPlanItemResponse, status_code=status.HTTP_201_CREATED)
async def add_plan_item(
    plan_id: uuid.UUID,
    payload: TestPlanItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = await db.get(TestPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Test plan not found")
    item = TestPlanItem(plan_id=plan_id, **payload.model_dump(exclude_unset=True))
    db.add(item)
    await db.flush()
    plan.total_cases += 1
    await db.commit()
    await db.refresh(item)
    return _row(item, TestPlanItemResponse)


@router.delete("/plans/{plan_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_plan_item(
    plan_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    item = await db.get(TestPlanItem, item_id)
    if not item or item.plan_id != plan_id:
        raise HTTPException(status_code=404, detail="Item not found")
    plan = await db.get(TestPlan, plan_id)
    if plan:
        plan.total_cases = max(0, plan.total_cases - 1)
    await db.delete(item)
    await db.commit()


@router.patch("/plans/{plan_id}/items/{item_id}/execute", response_model=TestPlanItemResponse)
async def record_execution(
    plan_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ExecuteTestPlanItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Record execution result for a test plan item."""
    item = await db.get(TestPlanItem, item_id)
    if not item or item.plan_id != plan_id:
        raise HTTPException(status_code=404, detail="Item not found")

    item.execution_status = payload.execution_status
    item.executed_by_id = current_user.id
    item.executed_at = datetime.now(timezone.utc)
    item.execution_notes = payload.execution_notes
    item.actual_duration_minutes = payload.actual_duration_minutes

    # Recompute plan aggregates
    plan = await db.get(TestPlan, plan_id)
    if plan:
        all_items_q = select(TestPlanItem).where(TestPlanItem.plan_id == plan_id)
        all_items_result = await db.execute(all_items_q)
        all_items = all_items_result.scalars().all()
        plan.executed_cases = sum(1 for i in all_items if i.execution_status not in ("not_run",))
        plan.passed_cases = sum(1 for i in all_items if i.execution_status == "passed")
        plan.failed_cases = sum(1 for i in all_items if i.execution_status == "failed")
        plan.blocked_cases = sum(1 for i in all_items if i.execution_status == "blocked")

    await db.commit()
    await db.refresh(item)
    return _row(item, TestPlanItemResponse)


@router.post("/plans/ai-create", response_model=TestPlanResponse, status_code=status.HTTP_201_CREATED)
async def ai_create_plan(
    payload: AIOptimizePlanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """AI creates an optimized test plan from approved test cases for a project."""
    from app.services.test_case_ai_agent import ai_optimize_plan

    q = select(ManagedTestCase).where(
        ManagedTestCase.project_id == payload.project_id,
        ManagedTestCase.status.in_(["approved", "active"]),
    )
    result = await db.execute(q)
    cases = result.scalars().all()
    if not cases:
        raise HTTPException(status_code=400, detail="No approved test cases found for this project")

    optimization = await ai_optimize_plan(
        [{"title": c.title, "priority": c.priority, "test_type": c.test_type,
          "estimated_duration_minutes": c.estimated_duration_minutes or 5} for c in cases],
        payload.constraints or "",
    )

    plan = TestPlan(
        project_id=payload.project_id,
        name=payload.plan_name or f"AI Test Plan — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        description=optimization.get("optimization_notes"),
        ai_generated=True,
        ai_generation_context=payload.constraints,
        created_by_id=current_user.id,
        total_cases=len(cases),
    )
    db.add(plan)
    await db.flush()

    # Build ordered case map from optimization
    order_map: dict[str, int] = {}
    for entry in optimization.get("optimized_order", []):
        order_map[entry.get("title", "")] = entry.get("execution_order", 999)

    for tc in cases:
        item = TestPlanItem(
            plan_id=plan.id,
            test_case_id=tc.id,
            order_index=order_map.get(tc.title, 999),
        )
        db.add(item)

    await _audit(db, "test_plan", plan.id, payload.project_id, "ai_generated", current_user,
                 details="AI-optimized test plan created")
    await db.commit()
    await db.refresh(plan)
    return _row(plan, TestPlanResponse)


# ── Test Strategies ───────────────────────────────────────────────────────────

@router.get("/strategies", response_model=list[TestStrategyResponse])
async def list_strategies(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(TestStrategy).where(TestStrategy.project_id == project_id).order_by(TestStrategy.created_at.desc())
    result = await db.execute(q)
    return [_row(s, TestStrategyResponse) for s in result.scalars().all()]


@router.post("/strategies/ai-generate", response_model=TestStrategyResponse, status_code=status.HTTP_201_CREATED)
async def ai_generate_strategy(
    payload: AIGenerateStrategyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Use AI to generate a comprehensive test strategy document."""
    from app.services.test_case_ai_agent import ai_generate_strategy
    result = await ai_generate_strategy(payload.project_context)

    from app.core.config import settings
    strategy = TestStrategy(
        project_id=payload.project_id,
        name=payload.strategy_name or f"Test Strategy — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        version_label="v1.0",
        status="draft",
        objective=result.get("objective"),
        scope=result.get("scope"),
        out_of_scope=result.get("out_of_scope"),
        test_approach=result.get("test_approach"),
        risk_assessment=result.get("risk_assessment"),
        test_types=result.get("test_types"),
        entry_criteria=result.get("entry_criteria"),
        exit_criteria=result.get("exit_criteria"),
        environments=result.get("environments"),
        automation_approach=result.get("automation_approach"),
        defect_management=result.get("defect_management"),
        ai_generated=True,
        generation_context=payload.project_context,
        ai_model_used=settings.LLM_MODEL,
        created_by_id=current_user.id,
    )
    db.add(strategy)
    await db.flush()
    await _audit(db, "test_strategy", strategy.id, payload.project_id, "ai_generated", current_user,
                 details="AI-generated test strategy")
    await db.commit()
    await db.refresh(strategy)
    return _row(strategy, TestStrategyResponse)


@router.get("/strategies/{strategy_id}", response_model=TestStrategyResponse)
async def get_strategy(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    s = await db.get(TestStrategy, strategy_id)
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return _row(s, TestStrategyResponse)


@router.put("/strategies/{strategy_id}", response_model=TestStrategyResponse)
async def update_strategy(
    strategy_id: uuid.UUID,
    payload: TestStrategyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    s = await db.get(TestStrategy, strategy_id)
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    await _audit(db, "test_strategy", s.id, s.project_id, "updated", current_user)
    await db.commit()
    await db.refresh(s)
    return _row(s, TestStrategyResponse)


# ── Audit Log ─────────────────────────────────────────────────────────────────

@router.get("/audit", response_model=AuditLogListResponse)
async def get_audit_log(
    project_id: uuid.UUID,
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Compliance audit trail for all test management actions."""
    q = select(TestCaseAuditLog).where(TestCaseAuditLog.project_id == project_id)
    if entity_type:
        q = q.where(TestCaseAuditLog.entity_type == entity_type)
    if action:
        q = q.where(TestCaseAuditLog.action == action)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    q = q.order_by(TestCaseAuditLog.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    return {
        "items": [_row(entry, AuditLogResponse) for entry in result.scalars().all()],
        "total": total, "page": page, "size": size, "pages": -(-total // size),
    }
