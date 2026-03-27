"""Test run and test case list endpoints."""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.models.postgres import TestCase, TestRun
from app.models.schemas import TestCaseListResponse

router = APIRouter(prefix="/api/v1/runs", tags=["Test Runs"])


def _enrich_with_release(runs: list, release_map: dict) -> list[dict]:
    """Attach release_name / release_id to each run dict."""
    out = []
    for run in runs:
        if hasattr(run, "__table__"):
            d = {c.name: getattr(run, c.name) for c in run.__table__.columns}
            for k, v in d.items():
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
                elif hasattr(v, "__str__") and isinstance(v, uuid.UUID):
                    d[k] = str(v)
        else:
            d = dict(run)
        run_id = str(d.get("id", ""))
        info = release_map.get(run_id, {})
        d["release_name"] = info.get("name")
        d["release_id"]   = info.get("id")
        out.append(d)
    return out


async def _fetch_release_map(db: AsyncSession, run_ids: list[str]) -> dict:
    """Return {run_id: {id, name}} for all linked releases."""
    if not run_ids:
        return {}
    try:
        # Build a VALUES list so asyncpg receives individual UUID strings,
        # avoiding array-binding issues with ANY(:ids::uuid[]).
        placeholders = ", ".join(f"'{rid}'::uuid" for rid in run_ids)
        query = text(f"""
            SELECT rtr.test_run_id::text AS run_id,
                   r.id::text            AS release_id,
                   r.name                AS release_name
            FROM release_test_run_links rtr
            JOIN releases r ON r.id = rtr.release_id
            WHERE rtr.test_run_id IN ({placeholders})
        """)
        rows = (await db.execute(query)).fetchall()
        return {r.run_id: {"id": r.release_id, "name": r.release_name} for r in rows}
    except Exception as exc:
        # Release tables may not exist yet (pending migration) — don't break runs endpoint
        logger.debug("Release map fetch skipped: %s", exc)
        return {}


@router.get("")
async def list_runs(
    project_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    release_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of test runs for a project, with optional release filter."""
    query = select(TestRun).where(TestRun.project_id == project_id)
    if status:
        query = query.where(TestRun.status == status)

    # Filter by release if requested
    if release_id:
        from app.models.postgres import ReleaseTestRunLink
        linked_ids_q = select(ReleaseTestRunLink.test_run_id).where(
            ReleaseTestRunLink.release_id == uuid.UUID(release_id)
        )
        query = query.where(TestRun.id.in_(linked_ids_q))

    query = query.order_by(TestRun.created_at.desc())

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    runs = result.scalars().all()

    run_ids = [str(r.id) for r in runs]
    release_map = await _fetch_release_map(db, run_ids)

    return {
        "items": _enrich_with_release(runs, release_map),
        "total": total,
        "page": page,
        "size": size,
        "pages": -(-total // size),
    }


@router.get("/{run_id}")
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single test run by ID, including linked release info."""
    result = await db.execute(select(TestRun).where(TestRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    release_map = await _fetch_release_map(db, [str(run_id)])
    enriched = _enrich_with_release([run], release_map)
    return enriched[0]


@router.get("/{run_id}/tests", response_model=TestCaseListResponse)
async def list_test_cases(
    run_id: uuid.UUID,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    status: str | None = None,
    suite: str | None = None,
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
    total = count_result.scalar() or 0

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


@router.post("/{run_id}/release")
async def set_run_release(
    run_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Link a test run to a release by name.
    If the release does not exist it is auto-created in 'planning' status.
    Body: {"release_name": "v2.5.0"}
    """
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
        "release_id":   str(release.id),
        "release_name": release.name,
        "release_status": release.status,
        "auto_created": created,
    }
