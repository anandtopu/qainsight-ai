"""Full-text search endpoint."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.models.postgres import TestCase, TestRun

router = APIRouter(prefix="/api/v1/search", tags=["Search"])


@router.get("")
async def search_test_cases(
    q: str = Query(..., min_length=1),
    project_id: str = None,
    status: str = None,
    days: int = Query(None, ge=1, le=365),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Full-text search across test names, suite names, class names, and error messages.
    Uses PostgreSQL tsvector for fast indexed search.
    """
    # Build dynamic query
    conditions = ["tc.test_name ILIKE :pattern OR tc.suite_name ILIKE :pattern OR tc.error_message ILIKE :pattern"]
    params: dict = {"pattern": f"%{q}%", "offset": (page - 1) * size, "limit": size}

    if project_id:
        conditions.append("tr.project_id = :project_id")
        params["project_id"] = project_id

    if status:
        conditions.append("tc.status = :status")
        params["status"] = status.upper()

    if days:
        conditions.append("tc.created_at >= NOW() - INTERVAL ':days days'")
        params["days"] = days

    where_clause = " AND ".join(conditions)
    query = text(f"""
        SELECT
            tc.id            AS test_case_id,
            tc.test_run_id,
            tc.test_name,
            tc.suite_name,
            tc.status,
            tc.created_at    AS last_run_date,
            COUNT(*) FILTER (WHERE tc2.status = 'FAILED') AS failure_count
        FROM test_cases tc
        JOIN test_runs tr ON tr.id = tc.test_run_id
        LEFT JOIN test_cases tc2 ON tc2.test_fingerprint = tc.test_fingerprint
        WHERE {where_clause}
        GROUP BY tc.id, tc.test_run_id, tc.test_name, tc.suite_name, tc.status, tc.created_at
        ORDER BY tc.created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    count_query = text(f"""
        SELECT COUNT(DISTINCT tc.id)
        FROM test_cases tc
        JOIN test_runs tr ON tr.id = tc.test_run_id
        WHERE {where_clause}
    """)

    results = await db.execute(query, params)
    rows = results.fetchall()

    count_result = await db.execute(count_query, {k: v for k, v in params.items() if k not in ("offset", "limit")})
    total = count_result.scalar() or 0

    return {
        "items": [dict(r._mapping) for r in rows],
        "total": total,
        "query": q,
        "search_type": "keyword",
        "page": page,
        "size": size,
        "pages": -(-total // size),
    }
