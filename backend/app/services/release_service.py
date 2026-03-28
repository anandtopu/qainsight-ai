from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.postgres import Release, ReleasePhase, ReleaseTestRunLink, TestRun


def serialize_model(obj) -> dict:
    data = {}
    for col in obj.__table__.columns:
        value = getattr(obj, col.name)
        if isinstance(value, uuid.UUID):
            data[col.name] = str(value)
        elif isinstance(value, datetime):
            data[col.name] = value.isoformat()
        else:
            data[col.name] = value
    return data


async def get_release_or_404(db: AsyncSession, release_id: str) -> Release:
    release = (
        await db.execute(select(Release).where(Release.id == uuid.UUID(release_id)))
    ).scalar_one_or_none()
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    return release


async def get_phase_or_404(db: AsyncSession, release_id: str, phase_id: str) -> ReleasePhase:
    phase = (
        await db.execute(
            select(ReleasePhase).where(
                ReleasePhase.id == uuid.UUID(phase_id),
                ReleasePhase.release_id == uuid.UUID(release_id),
            )
        )
    ).scalar_one_or_none()
    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")
    return phase


async def list_releases(db: AsyncSession, project_id: Optional[str], status: Optional[str] = None) -> dict:
    stmt = (
        select(Release)
        .options(selectinload(Release.phases))
        .order_by(Release.created_at.desc())
    )
    if project_id:
        stmt = stmt.where(Release.project_id == uuid.UUID(project_id))
    if status:
        stmt = stmt.where(Release.status == status)
    rows = (await db.execute(stmt)).scalars().all()

    items = []
    for release in rows:
        item = serialize_model(release)
        item["phases"] = [serialize_model(phase) for phase in release.phases]
        item["test_run_count"] = 0
        items.append(item)

    if items:
        ids = [release.id for release in rows]
        count_query = text(
            """
            SELECT release_id::text, COUNT(*) AS cnt
            FROM release_test_run_links
            WHERE release_id = ANY(:ids)
            GROUP BY release_id
            """
        )
        count_rows = (await db.execute(count_query, {"ids": ids})).fetchall()
        count_map = {row[0]: row[1] for row in count_rows}
        for item in items:
            item["test_run_count"] = count_map.get(item["id"], 0)

    return {"items": items, "total": len(items)}


async def create_release(db: AsyncSession, body) -> dict:
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

    for idx, phase_in in enumerate(body.phases):
        db.add(
            ReleasePhase(
                release_id=release.id,
                name=phase_in.name,
                phase_type=phase_in.phase_type,
                status=phase_in.status,
                description=phase_in.description,
                order_index=phase_in.order_index if phase_in.order_index else idx,
                planned_start=phase_in.planned_start,
                planned_end=phase_in.planned_end,
                exit_criteria=phase_in.exit_criteria,
                notes=phase_in.notes,
            )
        )

    await db.commit()
    stmt = select(Release).where(Release.id == release.id).options(selectinload(Release.phases))
    release = (await db.execute(stmt)).scalar_one()
    data = serialize_model(release)
    data["phases"] = [serialize_model(phase) for phase in release.phases]
    return data


async def get_release_details(db: AsyncSession, release_id: str) -> dict:
    stmt = (
        select(Release)
        .where(Release.id == uuid.UUID(release_id))
        .options(selectinload(Release.phases), selectinload(Release.test_run_links))
    )
    release = (await db.execute(stmt)).scalar_one_or_none()
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")

    data = serialize_model(release)
    data["phases"] = [serialize_model(phase) for phase in release.phases]

    if release.test_run_links:
        runs_query = text(
            """
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
            """
        )
        runs_rows = (await db.execute(runs_query, {"rel_id": release_id})).fetchall()
        data["linked_runs"] = [dict(row._mapping) for row in runs_rows]
    else:
        data["linked_runs"] = []

    agg_query = text(
        """
        SELECT
            COUNT(tr.id) AS total_runs,
            SUM(tr.total_tests) AS total_tests,
            SUM(tr.passed_tests) AS total_passed,
            SUM(tr.failed_tests) AS total_failed,
            ROUND(AVG(tr.pass_rate)::numeric, 1) AS avg_pass_rate
        FROM test_runs tr
        JOIN release_test_run_links rtr ON rtr.test_run_id = tr.id
        WHERE rtr.release_id = :rel_id
        """
    )
    agg = (await db.execute(agg_query, {"rel_id": release_id})).one()
    metrics = dict(agg._mapping)
    for key, value in metrics.items():
        if hasattr(value, "__float__") and not isinstance(value, (int, float, bool)):
            metrics[key] = float(value)
    data["metrics"] = metrics
    return data


async def update_release(db: AsyncSession, release_id: str, body) -> dict:
    release = await get_release_or_404(db, release_id)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(release, field, value)
    await db.commit()
    await db.refresh(release)
    return serialize_model(release)


async def delete_release(db: AsyncSession, release_id: str) -> None:
    release = await get_release_or_404(db, release_id)
    await db.delete(release)
    await db.commit()


async def add_phase(db: AsyncSession, release_id: str, body) -> dict:
    release = await get_release_or_404(db, release_id)
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
    return serialize_model(phase)


async def update_phase(db: AsyncSession, release_id: str, phase_id: str, body) -> dict:
    phase = await get_phase_or_404(db, release_id, phase_id)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(phase, field, value)
    await db.commit()
    await db.refresh(phase)
    return serialize_model(phase)


async def delete_phase(db: AsyncSession, release_id: str, phase_id: str) -> None:
    phase = await get_phase_or_404(db, release_id, phase_id)
    await db.delete(phase)
    await db.commit()


async def link_test_run(db: AsyncSession, release_id: str, body) -> dict:
    await get_release_or_404(db, release_id)
    run_uuid = uuid.UUID(body.test_run_id)
    run = (await db.execute(select(TestRun).where(TestRun.id == run_uuid))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    existing = (
        await db.execute(
            select(ReleaseTestRunLink).where(
                ReleaseTestRunLink.release_id == uuid.UUID(release_id),
                ReleaseTestRunLink.test_run_id == run_uuid,
            )
        )
    ).scalar_one_or_none()
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
    return serialize_model(link)


async def unlink_test_run(db: AsyncSession, release_id: str, run_id: str) -> None:
    link = (
        await db.execute(
            select(ReleaseTestRunLink).where(
                ReleaseTestRunLink.release_id == uuid.UUID(release_id),
                ReleaseTestRunLink.test_run_id == uuid.UUID(run_id),
            )
        )
    ).scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    await db.delete(link)
    await db.commit()
