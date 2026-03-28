"""Reports router — generate and email trend/analytics reports."""

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.services import report_service

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


class EmailTrendsRequest(BaseModel):
    project_id: str
    days: int = 30
    recipient_email: EmailStr
    chart_ids: list[str] = []


@router.post("/email-trends")
async def email_trends_report(
    body: EmailTrendsRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Generate and email a trends report for the specified project and period."""
    return await report_service.email_trends_report(db, body)
