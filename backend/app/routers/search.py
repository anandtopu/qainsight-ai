"""Keyword search endpoint for test cases."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.services.search_service import search_test_cases_query

router = APIRouter(prefix="/api/v1/search", tags=["Search"])


@router.get("")
async def search_test_cases(
    q: str = Query(..., min_length=1),
    project_id: str | None = None,
    status: str | None = None,
    days: int = Query(None, ge=1, le=365),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Keyword search across test names, suite names, and error messages.
    Uses SQLAlchemy query construction with ILIKE filters.
    """
    items, total, pages = await search_test_cases_query(
        db,
        q=q,
        page=page,
        size=size,
        project_id=project_id,
        status=status,
        days=days,
    )
    return {
        "items": items,
        "total": total,
        "query": q,
        "search_type": "keyword",
        "page": page,
        "size": size,
        "pages": pages,
    }
