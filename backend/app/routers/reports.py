"""Reports router — generate and email trend/analytics reports."""
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.postgres import get_db

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


class EmailTrendsRequest(BaseModel):
    project_id: str
    days: int = 30
    recipient_email: EmailStr
    chart_ids: list[str] = []


CHART_LABELS = {
    "daily_breakdown":   "Daily Breakdown",
    "pass_rate_trend":   "Pass Rate Trend",
    "cumulative_volume": "Cumulative Volume",
    "failure_rate":      "Failure Rate",
    "broken_trend":      "Broken Tests Trend",
    "skipped_trend":     "Skipped Tests Trend",
    "status_pie":        "Status Distribution",
}


async def _fetch_trend_data(db: AsyncSession, project_id: str, days: int) -> list[dict]:
    period_start = datetime.now(timezone.utc) - timedelta(days=days)
    query = text("""
        SELECT
            DATE_TRUNC('day', tr.created_at)::date::text   AS date,
            COUNT(*) FILTER (WHERE tc.status = 'PASSED')   AS passed,
            COUNT(*) FILTER (WHERE tc.status = 'FAILED')   AS failed,
            COUNT(*) FILTER (WHERE tc.status = 'SKIPPED')  AS skipped,
            COUNT(*) FILTER (WHERE tc.status = 'BROKEN')   AS broken,
            COUNT(*)                                         AS total,
            ROUND(
                COUNT(*) FILTER (WHERE tc.status = 'PASSED') * 100.0
                / NULLIF(COUNT(*), 0), 1
            )                                               AS pass_rate
        FROM test_cases tc
        JOIN test_runs tr ON tr.id = tc.test_run_id
        WHERE tr.project_id = :project_id
          AND tc.created_at >= :period_start
        GROUP BY 1
        ORDER BY 1
    """)
    result = await db.execute(query, {"project_id": str(project_id), "period_start": period_start})
    rows = result.fetchall()
    return [dict(r._mapping) for r in rows]


async def _fetch_project_name(db: AsyncSession, project_id: str) -> str:
    query = text("SELECT name FROM projects WHERE id = :pid OR slug = :pid LIMIT 1")
    result = await db.execute(query, {"pid": str(project_id)})
    row = result.fetchone()
    return row[0] if row else project_id


def _build_html_report(
    project_name: str,
    days: int,
    chart_ids: list[str],
    trend_data: list[dict],
) -> str:
    total_passed  = sum(r["passed"]  for r in trend_data)
    total_failed  = sum(r["failed"]  for r in trend_data)
    total_skipped = sum(r["skipped"] for r in trend_data)
    total_broken  = sum(r["broken"]  for r in trend_data)
    total_all     = sum(r["total"]   for r in trend_data)
    avg_pass_rate = (
        round(sum(float(r["pass_rate"] or 0) for r in trend_data) / len(trend_data), 1)
        if trend_data else 0
    )

    chart_list = "".join(f"<li>{CHART_LABELS.get(cid, cid)}</li>" for cid in chart_ids) if chart_ids else "<li>All charts</li>"

    rows_html = ""
    for r in trend_data:
        rows_html += f"""
        <tr>
            <td style="padding:6px 12px;border-bottom:1px solid #e5e7eb;">{r['date']}</td>
            <td style="padding:6px 12px;border-bottom:1px solid #e5e7eb;color:#059669;">{r['passed']}</td>
            <td style="padding:6px 12px;border-bottom:1px solid #e5e7eb;color:#dc2626;">{r['failed']}</td>
            <td style="padding:6px 12px;border-bottom:1px solid #e5e7eb;color:#d97706;">{r['skipped']}</td>
            <td style="padding:6px 12px;border-bottom:1px solid #e5e7eb;color:#ea580c;">{r['broken']}</td>
            <td style="padding:6px 12px;border-bottom:1px solid #e5e7eb;">{r['total']}</td>
            <td style="padding:6px 12px;border-bottom:1px solid #e5e7eb;font-weight:600;">{r['pass_rate']}%</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>QA Trends Report — {project_name}</title></head>
<body style="font-family:Arial,sans-serif;margin:0;padding:20px;background:#f9fafb;color:#111827;">
  <div style="max-width:800px;margin:0 auto;background:white;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1);">
    <div style="background:#1d4ed8;padding:24px 32px;">
      <h1 style="color:white;margin:0;font-size:22px;">QA Insight AI — Trends Report</h1>
      <p style="color:#bfdbfe;margin:4px 0 0;">Project: <strong>{project_name}</strong> &mdash; Last {days} days</p>
      <p style="color:#bfdbfe;margin:2px 0 0;font-size:12px;">Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
    </div>

    <div style="padding:24px 32px;">
      <h2 style="font-size:16px;margin:0 0 16px;">Summary KPIs</h2>
      <table style="width:100%;border-collapse:collapse;margin-bottom:24px;">
        <tr>
          <td style="padding:12px;background:#f0fdf4;border-radius:4px;text-align:center;">
            <div style="font-size:28px;font-weight:700;color:#059669;">{avg_pass_rate}%</div>
            <div style="font-size:11px;color:#6b7280;">Avg Pass Rate</div>
          </td>
          <td style="width:8px;"></td>
          <td style="padding:12px;background:#f0fdf4;border-radius:4px;text-align:center;">
            <div style="font-size:28px;font-weight:700;color:#059669;">{total_passed}</div>
            <div style="font-size:11px;color:#6b7280;">Total Passed</div>
          </td>
          <td style="width:8px;"></td>
          <td style="padding:12px;background:#fef2f2;border-radius:4px;text-align:center;">
            <div style="font-size:28px;font-weight:700;color:#dc2626;">{total_failed}</div>
            <div style="font-size:11px;color:#6b7280;">Total Failed</div>
          </td>
          <td style="width:8px;"></td>
          <td style="padding:12px;background:#fffbeb;border-radius:4px;text-align:center;">
            <div style="font-size:28px;font-weight:700;color:#d97706;">{total_skipped}</div>
            <div style="font-size:11px;color:#6b7280;">Total Skipped</div>
          </td>
          <td style="width:8px;"></td>
          <td style="padding:12px;background:#fff7ed;border-radius:4px;text-align:center;">
            <div style="font-size:28px;font-weight:700;color:#ea580c;">{total_broken}</div>
            <div style="font-size:11px;color:#6b7280;">Total Broken</div>
          </td>
        </tr>
      </table>

      <p style="font-size:13px;color:#6b7280;margin:0 0 8px;">Total executions in period: <strong>{total_all}</strong></p>
      <p style="font-size:13px;color:#6b7280;margin:0 0 16px;">Charts included: <ul style="margin:4px 0 0;padding-left:20px;font-size:13px;">{chart_list}</ul></p>

      <h2 style="font-size:16px;margin:24px 0 12px;">Daily Breakdown</h2>
      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead>
          <tr style="background:#f3f4f6;">
            <th style="padding:8px 12px;text-align:left;font-weight:600;">Date</th>
            <th style="padding:8px 12px;text-align:left;font-weight:600;color:#059669;">Passed</th>
            <th style="padding:8px 12px;text-align:left;font-weight:600;color:#dc2626;">Failed</th>
            <th style="padding:8px 12px;text-align:left;font-weight:600;color:#d97706;">Skipped</th>
            <th style="padding:8px 12px;text-align:left;font-weight:600;color:#ea580c;">Broken</th>
            <th style="padding:8px 12px;text-align:left;font-weight:600;">Total</th>
            <th style="padding:8px 12px;text-align:left;font-weight:600;">Pass Rate</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>

    <div style="padding:16px 32px;background:#f9fafb;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;">
      This report was generated automatically by QA Insight AI. Do not reply to this email.
    </div>
  </div>
</body>
</html>"""


def _send_email(recipient: str, subject: str, html_body: str) -> None:
    """Send an HTML email via SMTP."""
    if not settings.SMTP_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="SMTP is not enabled. Set SMTP_ENABLED=true and configure SMTP_* settings.",
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.SMTP_FROM
    msg["To"]      = recipient
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context() if settings.SMTP_TLS else None

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
        if settings.SMTP_TLS:
            server.starttls(context=context)
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, recipient, msg.as_string())


@router.post("/email-trends")
async def email_trends_report(
    body: EmailTrendsRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Generate and email a trends report for the specified project and period."""
    project_name = await _fetch_project_name(db, body.project_id)
    trend_data   = await _fetch_trend_data(db, body.project_id, body.days)

    html = _build_html_report(
        project_name=project_name,
        days=body.days,
        chart_ids=body.chart_ids,
        trend_data=trend_data,
    )

    subject = f"QA Trends Report — {project_name} ({body.days}d)"

    try:
        _send_email(body.recipient_email, subject, html)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {exc}") from exc

    return {"status": "sent", "recipient": body.recipient_email}
