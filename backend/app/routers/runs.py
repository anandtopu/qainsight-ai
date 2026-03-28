"""Test run and test case list endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.models.postgres import TestCase, TestRun
from app.models.schemas import TestCaseListResponse
from app.services.runs_service import get_run_with_release, list_project_runs, list_run_test_cases

router = APIRouter(prefix="/api/v1/runs", tags=["Test Runs"])


@router.get("")
async def list_runs(
    project_id: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    release_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    items, total, pages = await list_project_runs(db, project_id, page, size, status, release_id)
    return {"items": items, "total": total, "page": page, "size": size, "pages": pages}


@router.get("/{run_id}")
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    run = await get_run_with_release(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return run


@router.get("/{run_id}/tests", response_model=TestCaseListResponse)
async def list_test_cases(
    run_id: uuid.UUID,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    status: str | None = None,
    suite: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    items, total, pages = await list_run_test_cases(db, run_id, page, size, status, suite)
    return {"items": items, "total": total, "page": page, "size": size, "pages": pages}


@router.get("/{run_id}/tests/{test_id}")
async def get_test_case(
    run_id: uuid.UUID,
    test_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TestCase).where(
            TestCase.id == test_id,
            TestCase.test_run_id == run_id,
        )
    )
    test_case = result.scalar_one_or_none()
    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")
    return test_case


@router.post("/{run_id}/release")
async def set_run_release(
    run_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    release_name = (body.get("release_name") or "").strip()
    if not release_name:
        raise HTTPException(status_code=422, detail="release_name is required")

    run = (await db.execute(select(TestRun).where(TestRun.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    from app.services.release_linker import auto_link_release

    release, created = await auto_link_release(
        db=db,
        project_id=run.project_id,
        release_name=release_name,
        test_run_id=run.id,
    )
    await db.commit()

    return {
        "release_id": str(release.id),
        "release_name": release.name,
        "release_status": release.status,
        "auto_created": created,
    }
