"""Analytics endpoints: flaky tests, failure clusters, coverage, defects."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


# ── Flaky Test Leaderboard ─────────────────────────────────────────────────

@router.get("/flaky-tests")
async def flaky_tests(
    project_id: str,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Return tests with highest flakiness rate (intermittent pass/fail pattern)."""
    period_start = datetime.now(timezone.utc) - timedelta(days=days)
    query = text("""
        SELECT
            tch.test_fingerprint,
            MAX(tc.test_name)   AS test_name,
            MAX(tc.suite_name)  AS suite_name,
            MAX(tc.class_name)  AS class_name,
            COUNT(*)            AS total_runs,
            COUNT(*) FILTER (WHERE tch.status IN ('FAILED', 'BROKEN')) AS fail_count,
            COUNT(*) FILTER (WHERE tch.status = 'PASSED')              AS pass_count,
            ROUND(
                COUNT(*) FILTER (WHERE tch.status IN ('FAILED', 'BROKEN')) * 100.0 / COUNT(*), 1
            ) AS failure_rate_pct,
            MAX(tch.created_at) AS last_seen
        FROM test_case_history tch
        JOIN test_cases tc ON tc.id = tch.test_case_id
        JOIN test_runs tr   ON tr.id = tch.test_run_id
        WHERE tr.project_id = :project_id
          AND tch.created_at >= :period_start
        GROUP BY tch.test_fingerprint
        HAVING COUNT(*) >= 3
           AND COUNT(*) FILTER (WHERE tch.status IN ('FAILED', 'BROKEN')) * 1.0 / COUNT(*) BETWEEN 0.05 AND 0.95
        ORDER BY failure_rate_pct DESC
        LIMIT :limit
    """)
    result = await db.execute(query, {"project_id": str(project_id), "period_start": period_start, "limit": limit})
    rows = result.fetchall()
    return {
        "items": [dict(r._mapping) for r in rows],
        "period_days": days,
        "total": len(rows),
    }


# ── Failure Category Distribution ─────────────────────────────────────────

@router.get("/failure-categories")
async def failure_categories(
    project_id: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Return distribution of failure categories for AI-analysed test cases."""
    period_start = datetime.now(timezone.utc) - timedelta(days=days)
    query = text("""
        SELECT
            COALESCE(tc.failure_category, 'UNKNOWN') AS category,
            COUNT(*) AS count
        FROM test_cases tc
        JOIN test_runs tr ON tr.id = tc.test_run_id
        WHERE tr.project_id = :project_id
          AND tc.status IN ('FAILED', 'BROKEN')
          AND tc.created_at >= :period_start
        GROUP BY category
        ORDER BY count DESC
    """)
    result = await db.execute(query, {"project_id": str(project_id), "period_start": period_start})
    rows = result.fetchall()
    return {"items": [dict(r._mapping) for r in rows], "period_days": days}


# ── Top Failing Tests ──────────────────────────────────────────────────────

@router.get("/top-failing")
async def top_failing_tests(
    project_id: str,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(15, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Return tests with the highest total failure count in the period."""
    period_start = datetime.now(timezone.utc) - timedelta(days=days)
    query = text("""
        SELECT
            tc.test_fingerprint,
            MAX(tc.test_name)   AS test_name,
            MAX(tc.suite_name)  AS suite_name,
            MAX(tc.class_name)  AS class_name,
            MAX(tc.failure_category) AS failure_category,
            COUNT(*) AS fail_count,
            MAX(tc.created_at)  AS last_failed
        FROM test_cases tc
        JOIN test_runs tr ON tr.id = tc.test_run_id
        WHERE tr.project_id = :project_id
          AND tc.status IN ('FAILED', 'BROKEN')
          AND tc.created_at >= :period_start
        GROUP BY tc.test_fingerprint
        ORDER BY fail_count DESC
        LIMIT :limit
    """)
    result = await db.execute(query, {"project_id": str(project_id), "period_start": period_start, "limit": limit})
    rows = result.fetchall()
    return {"items": [dict(r._mapping) for r in rows], "period_days": days}


# ── Coverage Snapshot ──────────────────────────────────────────────────────

@router.get("/coverage")
async def coverage_stats(
    project_id: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Return test suite coverage stats aggregated over the period."""
    period_start = datetime.now(timezone.utc) - timedelta(days=days)

    # Suite breakdown
    suite_query = text("""
        SELECT
            COALESCE(tc.suite_name, 'Unknown Suite') AS suite_name,
            COUNT(DISTINCT tc.test_fingerprint)      AS unique_tests,
            COUNT(*) FILTER (WHERE tc.status = 'PASSED') AS passed,
            COUNT(*) FILTER (WHERE tc.status IN ('FAILED', 'BROKEN')) AS failed,
            COUNT(*) FILTER (WHERE tc.status = 'SKIPPED') AS skipped,
            ROUND(
                COUNT(*) FILTER (WHERE tc.status = 'PASSED') * 100.0 / NULLIF(COUNT(*), 0), 1
            ) AS pass_rate
        FROM test_cases tc
        JOIN test_runs tr ON tr.id = tc.test_run_id
        WHERE tr.project_id = :project_id
          AND tc.created_at >= :period_start
        GROUP BY tc.suite_name
        ORDER BY unique_tests DESC
        LIMIT 50
    """)
    suite_result = await db.execute(suite_query, {"project_id": str(project_id), "period_start": period_start})
    suites = suite_result.fetchall()

    # Total stats
    total_query = text("""
        SELECT
            COUNT(DISTINCT tc.test_fingerprint)  AS unique_tests,
            COUNT(DISTINCT tc.suite_name)        AS suite_count,
            COUNT(*)                              AS total_executions,
            ROUND(AVG(tr.pass_rate)::numeric, 1)  AS avg_pass_rate,
            COUNT(DISTINCT DATE_TRUNC('day', tr.created_at)) AS days_with_runs
        FROM test_cases tc
        JOIN test_runs tr ON tr.id = tc.test_run_id
        WHERE tr.project_id = :project_id
          AND tc.created_at >= :period_start
    """)
    total_result = await db.execute(total_query, {"project_id": str(project_id), "period_start": period_start})
    total = total_result.one()

    return {
        "summary": dict(total._mapping),
        "suites": [dict(r._mapping) for r in suites],
        "period_days": days,
    }


# ── Suite Detail ───────────────────────────────────────────────────────────

@router.get("/suite-detail")
async def suite_detail(
    project_id: str,
    suite_name: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """
    Return detailed breakdown for a single test suite:
      - Summary KPIs (unique tests, executions, pass rate, avg duration)
      - Per-test-case aggregates with flakiness flag
      - Last 10 test runs that included this suite
    """
    period_start = datetime.now(timezone.utc) - timedelta(days=days)
    params = {
        "project_id": str(project_id),
        "suite_name":  suite_name,
        "period_start": period_start,
    }

    # ── Suite-level summary ────────────────────────────────────────────────
    summary_query = text("""
        SELECT
            COUNT(DISTINCT tc.test_fingerprint)                              AS unique_tests,
            COUNT(*)                                                          AS total_executions,
            COUNT(*) FILTER (WHERE tc.status = 'PASSED')                     AS passed,
            COUNT(*) FILTER (WHERE tc.status IN ('FAILED', 'BROKEN'))        AS failed,
            COUNT(*) FILTER (WHERE tc.status = 'SKIPPED')                    AS skipped,
            ROUND(
                COUNT(*) FILTER (WHERE tc.status = 'PASSED') * 100.0
                / NULLIF(COUNT(*), 0), 1
            )                                                                 AS pass_rate,
            ROUND(AVG(tc.duration_ms)::numeric, 0)                           AS avg_duration_ms,
            MAX(tc.created_at)                                                AS last_run_at
        FROM test_cases tc
        JOIN test_runs tr ON tr.id = tc.test_run_id
        WHERE tr.project_id    = :project_id
          AND COALESCE(tc.suite_name, 'Unknown Suite') = :suite_name
          AND tc.created_at   >= :period_start
    """)
    summary_row = (await db.execute(summary_query, params)).one()

    # ── Per-test-case breakdown ────────────────────────────────────────────
    cases_query = text("""
        SELECT
            tc.test_fingerprint,
            MAX(tc.test_name)                                                 AS test_name,
            MAX(tc.class_name)                                                AS class_name,
            COUNT(*)                                                          AS total_executions,
            COUNT(*) FILTER (WHERE tc.status = 'PASSED')                     AS passed,
            COUNT(*) FILTER (WHERE tc.status IN ('FAILED', 'BROKEN'))        AS failed,
            COUNT(*) FILTER (WHERE tc.status = 'SKIPPED')                    AS skipped,
            ROUND(
                COUNT(*) FILTER (WHERE tc.status = 'PASSED') * 100.0
                / NULLIF(COUNT(*), 0), 1
            )                                                                 AS pass_rate,
            ROUND(AVG(tc.duration_ms)::numeric, 0)                           AS avg_duration_ms,
            (array_agg(tc.status  ORDER BY tc.created_at DESC))[1]           AS last_status,
            (array_agg(tc.error_message ORDER BY tc.created_at DESC))[1]     AS last_error,
            MAX(tc.created_at)                                                AS last_run_at,
            (
                COUNT(*) >= 3
                AND COUNT(*) FILTER (WHERE tc.status IN ('FAILED', 'BROKEN'))
                    * 1.0 / NULLIF(COUNT(*), 0) BETWEEN 0.05 AND 0.95
            )                                                                 AS is_flaky
        FROM test_cases tc
        JOIN test_runs tr ON tr.id = tc.test_run_id
        WHERE tr.project_id    = :project_id
          AND COALESCE(tc.suite_name, 'Unknown Suite') = :suite_name
          AND tc.created_at   >= :period_start
        GROUP BY tc.test_fingerprint
        ORDER BY failed DESC, total_executions DESC
        LIMIT 200
    """)
    cases_rows = (await db.execute(cases_query, params)).fetchall()

    # ── Recent runs containing this suite ─────────────────────────────────
    runs_query = text("""
        SELECT
            tr.id::text                                                       AS test_run_id,
            tr.build_number,
            tr.created_at                                                     AS run_date,
            COUNT(*) FILTER (WHERE tc.status = 'PASSED')                     AS passed,
            COUNT(*) FILTER (WHERE tc.status IN ('FAILED', 'BROKEN'))        AS failed,
            COUNT(*) FILTER (WHERE tc.status = 'SKIPPED')                    AS skipped,
            ROUND(
                COUNT(*) FILTER (WHERE tc.status = 'PASSED') * 100.0
                / NULLIF(COUNT(*), 0), 1
            )                                                                 AS pass_rate
        FROM test_runs tr
        JOIN test_cases tc ON tc.test_run_id = tr.id
        WHERE tr.project_id    = :project_id
          AND COALESCE(tc.suite_name, 'Unknown Suite') = :suite_name
          AND tr.created_at   >= :period_start
        GROUP BY tr.id, tr.build_number, tr.created_at
        ORDER BY tr.created_at DESC
        LIMIT 15
    """)
    runs_rows = (await db.execute(runs_query, params)).fetchall()

    def _row(r) -> dict:
        d = dict(r._mapping)
        # Coerce Decimal / datetime to JSON-safe types
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
            elif hasattr(v, "__float__") and not isinstance(v, (int, float, bool)):
                d[k] = float(v)
        return d

    return {
        "suite_name":  suite_name,
        "summary":     _row(summary_row),
        "test_cases":  [_row(r) for r in cases_rows],
        "recent_runs": [_row(r) for r in runs_rows],
        "period_days": days,
    }


# ── Defects List ───────────────────────────────────────────────────────────

@router.get("/defects")
async def list_defects(
    project_id: str,
    resolution_status: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Return defects for a project with optional resolution status filter."""
    query = text("""
        SELECT
            d.id,
            d.jira_ticket_id,
            d.jira_ticket_url,
            d.jira_status,
            d.failure_category,
            d.resolution_status,
            d.ai_confidence_score,
            d.created_at,
            d.resolved_at,
            tc.test_name,
            tc.suite_name
        FROM defects d
        JOIN test_cases tc ON tc.id = d.test_case_id
        WHERE d.project_id = :project_id
        {status_filter}
        ORDER BY d.created_at DESC
        LIMIT :limit OFFSET :offset
    """.format(status_filter="AND d.resolution_status = :resolution_status" if resolution_status else ""))

    params: dict = {
        "project_id": str(project_id),
        "limit": size,
        "offset": (page - 1) * size,
    }
    if resolution_status:
        params["resolution_status"] = resolution_status.upper()

    result = await db.execute(query, params)
    rows = result.fetchall()

    count_query = text("""
        SELECT COUNT(*) FROM defects d
        WHERE d.project_id = :project_id
        {status_filter}
    """.format(status_filter="AND d.resolution_status = :resolution_status" if resolution_status else ""))

    count_result = await db.execute(count_query, {k: v for k, v in params.items() if k not in ("limit", "offset")})
    total = count_result.scalar() or 0

    return {
        "items": [dict(r._mapping) for r in rows],
        "total": total,
        "page": page,
        "size": size,
        "pages": -(-total // size),
    }


# ── AI Analysis Summary ────────────────────────────────────────────────────

@router.get("/ai-summary")
async def ai_analysis_summary(
    project_id: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Return summary of AI analysis results for the project."""
    period_start = datetime.now(timezone.utc) - timedelta(days=days)
    query = text("""
        SELECT
            COUNT(*)                                              AS total_analysed,
            COUNT(*) FILTER (WHERE ai.confidence_score >= 80)    AS high_confidence,
            COUNT(*) FILTER (WHERE ai.is_flaky)                  AS flaky_detected,
            COUNT(*) FILTER (WHERE ai.backend_error_found)       AS backend_errors,
            COUNT(*) FILTER (WHERE ai.pod_issue_found)           AS pod_issues,
            COUNT(*) FILTER (WHERE ai.requires_human_review)     AS needs_review,
            ROUND(AVG(ai.confidence_score), 1)                   AS avg_confidence
        FROM ai_analysis ai
        JOIN test_cases tc ON tc.id = ai.test_case_id
        JOIN test_runs tr  ON tr.id = tc.test_run_id
        WHERE tr.project_id = :project_id
          AND ai.created_at >= :period_start
    """)
    result = await db.execute(query, {"project_id": str(project_id), "period_start": period_start})
    row = result.one()
    return dict(row._mapping)
