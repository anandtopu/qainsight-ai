"""Release management endpoints — CRUD for releases, phases, and test-run links."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.postgres import get_db
from app.models.postgres import Release, ReleasePhase, ReleaseTestRunLink, TestRun

router = APIRouter(prefix="/api/v1/releases", tags=["Releases"])


# ── Pydantic schemas ───────────────────────────────────────────────────────

class PhaseIn(BaseModel):
    name: str
    phase_type: str = "qa_testing"
    status: str = "pending"
    description: Optional[str] = None
    order_index: int = 0
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    exit_criteria: Optional[dict] = None
    notes: Optional[str] = None


class PhaseUpdate(BaseModel):
    name: Optional[str] = None
    phase_type: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    order_index: Optional[int] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    exit_criteria: Optional[dict] = None
    notes: Optional[str] = None


class ReleaseIn(BaseModel):
    project_id: str
    name: str
    version: Optional[str] = None
    description: Optional[str] = None
    status: str = "planning"
    planned_date: Optional[datetime] = None
    phases: list[PhaseIn] = []


class ReleaseUpdate(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    planned_date: Optional[datetime] = None
    released_at: Optional[datetime] = None


class LinkRunRequest(BaseModel):
    test_run_id: str
    phase_id: Optional[str] = None


# ── Helper ─────────────────────────────────────────────────────────────────

def _ser(obj) -> dict:
    """Serialize a SQLAlchemy ORM object to a plain dict."""
    d = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, uuid.UUID):
            d[col.name] = str(val)
        elif isinstance(val, datetime):
            d[col.name] = val.isoformat()
        else:
            d[col.name] = val
    return d


# ── List releases ──────────────────────────────────────────────────────────

@router.get("")
async def list_releases(
    project_id: str = Query(...),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Release)
        .where(Release.project_id == uuid.UUID(project_id))
        .options(selectinload(Release.phases))
        .order_by(Release.created_at.desc())
    )
    if status:
        stmt = stmt.where(Release.status == status)
    rows = (await db.execute(stmt)).scalars().all()

    items = []
    for r in rows:
        d = _ser(r)
        d["phases"] = [_ser(p) for p in r.phases]
        d["test_run_count"] = 0  # will be enriched below
        items.append(d)

    # Enrich with linked run counts
    if items:
        ids = [r.id for r in rows]
        count_query = text("""
            SELECT release_id::text, COUNT(*) AS cnt
            FROM release_test_run_links
            WHERE release_id = ANY(:ids)
            GROUP BY release_id
        """)
        count_rows = (await db.execute(count_query, {"ids": ids})).fetchall()
        count_map = {r[0]: r[1] for r in count_rows}
        for item in items:
            item["test_run_count"] = count_map.get(item["id"], 0)

    return {"items": items, "total": len(items)}


# ── Create release ─────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_release(body: ReleaseIn, db: AsyncSession = Depends(get_db)):
    release = Release(
        project_id=uuid.UUID(body.project_id),
        name=body.name,
        version=body.version,
        description=body.description,
        status=body.status,
        planned_date=body.planned_date,
    )
    db.add(release)
    await db.flush()

    for idx, p in enumerate(body.phases):
        phase = ReleasePhase(
            release_id=release.id,
            name=p.name,
            phase_type=p.phase_type,
            status=p.status,
            description=p.description,
            order_index=p.order_index if p.order_index else idx,
            planned_start=p.planned_start,
            planned_end=p.planned_end,
            exit_criteria=p.exit_criteria,
            notes=p.notes,
        )
        db.add(phase)

    await db.commit()
    await db.refresh(release)

    # Re-fetch with phases
    stmt = select(Release).where(Release.id == release.id).options(selectinload(Release.phases))
    release = (await db.execute(stmt)).scalar_one()
    d = _ser(release)
    d["phases"] = [_ser(p) for p in release.phases]
    return d


# ── Get single release ─────────────────────────────────────────────────────

@router.get("/{release_id}")
async def get_release(release_id: str, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Release)
        .where(Release.id == uuid.UUID(release_id))
        .options(selectinload(Release.phases), selectinload(Release.test_run_links))
    )
    release = (await db.execute(stmt)).scalar_one_or_none()
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")

    d = _ser(release)
    d["phases"] = [_ser(p) for p in release.phases]

    # Linked runs with aggregated metrics
    if release.test_run_links:
        run_ids = [str(link.test_run_id) for link in release.test_run_links]
        runs_query = text("""
            SELECT
                tr.id::text, tr.build_number, tr.status,
                tr.total_tests, tr.passed_tests, tr.failed_tests,
                tr.broken_tests, tr.skipped_tests, tr.pass_rate,
                tr.created_at,
                rtr.phase_id::text AS phase_id
            FROM test_runs tr
            JOIN release_test_run_links rtr ON rtr.test_run_id = tr.id
            WHERE rtr.release_id = :rel_id
            ORDER BY tr.created_at DESC
        """)
        runs_rows = (await db.execute(runs_query, {"rel_id": release_id})).fetchall()
        d["linked_runs"] = [dict(r._mapping) for r in runs_rows]
    else:
        d["linked_runs"] = []

    # Aggregate metrics across all linked runs
    agg_query = text("""
        SELECT
            COUNT(tr.id)                AS total_runs,
            SUM(tr.total_tests)         AS total_tests,
            SUM(tr.passed_tests)        AS total_passed,
            SUM(tr.failed_tests)        AS total_failed,
            ROUND(AVG(tr.pass_rate)::numeric, 1) AS avg_pass_rate
        FROM test_runs tr
        JOIN release_test_run_links rtr ON rtr.test_run_id = tr.id
        WHERE rtr.release_id = :rel_id
    """)
    agg = (await db.execute(agg_query, {"rel_id": release_id})).one()
    agg_d = dict(agg._mapping)
    for k, v in agg_d.items():
        if hasattr(v, "__float__") and not isinstance(v, (int, float, bool)):
            agg_d[k] = float(v)
    d["metrics"] = agg_d

    return d


# ── Update release ─────────────────────────────────────────────────────────

@router.put("/{release_id}")
async def update_release(
    release_id: str, body: ReleaseUpdate, db: AsyncSession = Depends(get_db),
):
    release = (await db.execute(
        select(Release).where(Release.id == uuid.UUID(release_id))
    )).scalar_one_or_none()
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")

    for field, val in body.model_dump(exclude_none=True).items():
        setattr(release, field, val)

    await db.commit()
    await db.refresh(release)
    return _ser(release)


# ── Delete release ─────────────────────────────────────────────────────────

@router.delete("/{release_id}", status_code=204)
async def delete_release(release_id: str, db: AsyncSession = Depends(get_db)):
    release = (await db.execute(
        select(Release).where(Release.id == uuid.UUID(release_id))
    )).scalar_one_or_none()
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    await db.delete(release)
    await db.commit()


# ── Phase CRUD ─────────────────────────────────────────────────────────────

@router.post("/{release_id}/phases", status_code=201)
async def add_phase(
    release_id: str, body: PhaseIn, db: AsyncSession = Depends(get_db),
):
    release = (await db.execute(
        select(Release).where(Release.id == uuid.UUID(release_id))
    )).scalar_one_or_none()
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")

    phase = ReleasePhase(
        release_id=release.id,
        name=body.name,
        phase_type=body.phase_type,
        status=body.status,
        description=body.description,
        order_index=body.order_index,
        planned_start=body.planned_start,
        planned_end=body.planned_end,
        actual_start=body.actual_start,
        actual_end=body.actual_end,
        exit_criteria=body.exit_criteria,
        notes=body.notes,
    )
    db.add(phase)
    await db.commit()
    await db.refresh(phase)
    return _ser(phase)


@router.put("/{release_id}/phases/{phase_id}")
async def update_phase(
    release_id: str, phase_id: str, body: PhaseUpdate, db: AsyncSession = Depends(get_db),
):
    phase = (await db.execute(
        select(ReleasePhase).where(
            ReleasePhase.id == uuid.UUID(phase_id),
            ReleasePhase.release_id == uuid.UUID(release_id),
        )
    )).scalar_one_or_none()
    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")

    for field, val in body.model_dump(exclude_none=True).items():
        setattr(phase, field, val)

    await db.commit()
    await db.refresh(phase)
    return _ser(phase)


@router.delete("/{release_id}/phases/{phase_id}", status_code=204)
async def delete_phase(
    release_id: str, phase_id: str, db: AsyncSession = Depends(get_db),
):
    phase = (await db.execute(
        select(ReleasePhase).where(
            ReleasePhase.id == uuid.UUID(phase_id),
            ReleasePhase.release_id == uuid.UUID(release_id),
        )
    )).scalar_one_or_none()
    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")
    await db.delete(phase)
    await db.commit()


# ── Link test runs ──────────────────────────────────────────────────────────

@router.post("/{release_id}/test-runs")
async def link_test_run(
    release_id: str, body: LinkRunRequest, db: AsyncSession = Depends(get_db),
):
    # Verify release exists
    release = (await db.execute(
        select(Release).where(Release.id == uuid.UUID(release_id))
    )).scalar_one_or_none()
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")

    # Verify run exists
    run_uuid = uuid.UUID(body.test_run_id)
    run = (await db.execute(select(TestRun).where(TestRun.id == run_uuid))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    # Check duplicate
    existing = (await db.execute(
        select(ReleaseTestRunLink).where(
            ReleaseTestRunLink.release_id == uuid.UUID(release_id),
            ReleaseTestRunLink.test_run_id == run_uuid,
        )
    )).scalar_one_or_none()
    if existing:
        return {"message": "Already linked", "id": str(existing.id)}

    link = ReleaseTestRunLink(
        release_id=uuid.UUID(release_id),
        test_run_id=run_uuid,
        phase_id=uuid.UUID(body.phase_id) if body.phase_id else None,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return _ser(link)


@router.delete("/{release_id}/test-runs/{run_id}", status_code=204)
async def unlink_test_run(
    release_id: str, run_id: str, db: AsyncSession = Depends(get_db),
):
    link = (await db.execute(
        select(ReleaseTestRunLink).where(
            ReleaseTestRunLink.release_id == uuid.UUID(release_id),
            ReleaseTestRunLink.test_run_id == uuid.UUID(run_id),
        )
    )).scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    await db.delete(link)
    await db.commit()
