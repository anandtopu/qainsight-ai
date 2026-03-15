"""Test run and test case list endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.models.postgres import TestCase, TestRun
from app.models.schemas import TestCaseListResponse, TestRunListResponse

router = APIRouter(prefix="/api/v1/runs", tags=["Test Runs"])


@router.get("", response_model=TestRunListResponse)
async def list_runs(
    project_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of Jenkins build runs for a project."""
    query = select(TestRun).where(TestRun.project_id == project_id)
    if status:
        query = query.where(TestRun.status == status)
    query = query.order_by(TestRun.created_at.desc())

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    runs = result.scalars().all()

    return {
        "items": runs,
        "total": total,
        "page": page,
        "size": size,
        "pages": -(-total // size),
    }


@router.get("/{run_id}")
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single test run by ID."""
    result = await db.execute(select(TestRun).where(TestRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return run


@router.get("/{run_id}/tests", response_model=TestCaseListResponse)
async def list_test_cases(
    run_id: uuid.UUID,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    status: str = None,
    suite: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of test cases within a run, with optional status/suite filters."""
    query = select(TestCase).where(TestCase.test_run_id == run_id)
    if status:
        query = query.where(TestCase.status == status.upper())
    if suite:
        query = query.where(TestCase.suite_name.ilike(f"%{suite}%"))
    query = query.order_by(TestCase.status, TestCase.test_name)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    cases = result.scalars().all()

    return {
        "items": cases,
        "total": total,
        "page": page,
        "size": size,
        "pages": -(-total // size),
    }


@router.get("/{run_id}/tests/{test_id}")
async def get_test_case(
    run_id: uuid.UUID,
    test_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information for a single test case."""
    result = await db.execute(
        select(TestCase).where(
            TestCase.id == test_id,
            TestCase.test_run_id == run_id,
        )
    )
    tc = result.scalar_one_or_none()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    return tc
