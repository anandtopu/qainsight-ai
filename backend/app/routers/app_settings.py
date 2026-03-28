"""Application settings management — SMTP configuration."""
import logging

import aiosmtplib  # type: ignore
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import require_role
from app.db.postgres import get_db
from app.models.postgres import AppSetting, User, UserRole
from app.models.schemas import SmtpConfigRead, SmtpConfigUpdate, SmtpTestResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])

_SMTP_KEY = "smtp_config"


async def _load_smtp_row(db: AsyncSession) -> dict:
    """Return the stored SMTP config dict, falling back to env-var defaults."""
    from sqlalchemy import select

    result = await db.execute(select(AppSetting).where(AppSetting.key == _SMTP_KEY))
    row = result.scalar_one_or_none()
    if row and row.value:
        return dict(row.value)
    # Env-var defaults
    return {
        "enabled": settings.SMTP_ENABLED,
        "host": settings.SMTP_HOST,
        "port": settings.SMTP_PORT,
        "user": settings.SMTP_USER,
        "password": settings.SMTP_PASSWORD,
        "from_address": settings.SMTP_FROM,
        "tls": settings.SMTP_TLS,
    }


@router.get("/smtp", response_model=SmtpConfigRead)
async def get_smtp_config(
    _: User = Depends(require_role(UserRole.QA_LEAD)),
    db: AsyncSession = Depends(get_db),
) -> SmtpConfigRead:
    """Return current SMTP configuration (password is never returned)."""
    cfg = await _load_smtp_row(db)
    return SmtpConfigRead(
        enabled=cfg.get("enabled", False),
        host=cfg.get("host", "localhost"),
        port=cfg.get("port", 587),
        user=cfg.get("user") or None,
        from_address=cfg.get("from_address", "noreply@qainsight.io"),
        tls=cfg.get("tls", True),
        password_set=bool(cfg.get("password")),
    )


@router.put("/smtp", response_model=SmtpConfigRead)
async def update_smtp_config(
    payload: SmtpConfigUpdate,
    _: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> SmtpConfigRead:
    """Persist SMTP configuration to the database."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    # Load existing config so we can preserve the password when not supplied
    existing = await _load_smtp_row(db)
    password = payload.password if payload.password is not None else existing.get("password")

    new_value = {
        "enabled": payload.enabled,
        "host": payload.host,
        "port": payload.port,
        "user": payload.user,
        "password": password,
        "from_address": payload.from_address,
        "tls": payload.tls,
    }

    stmt = pg_insert(AppSetting).values(key=_SMTP_KEY, value=new_value)
    stmt = stmt.on_conflict_do_update(index_elements=["key"], set_={"value": new_value})
    await db.execute(stmt)
    await db.commit()

    logger.info("SMTP configuration updated")
    return SmtpConfigRead(
        enabled=payload.enabled,
        host=payload.host,
        port=payload.port,
        user=payload.user or None,
        from_address=payload.from_address,
        tls=payload.tls,
        password_set=bool(password),
    )


@router.post("/smtp/test", response_model=SmtpTestResult)
async def test_smtp_config(
    current_user: User = Depends(require_role(UserRole.QA_LEAD)),
    db: AsyncSession = Depends(get_db),
) -> SmtpTestResult:
    """Send a test email to the current user's address using the stored SMTP config."""
    cfg = await _load_smtp_row(db)

    if not cfg.get("enabled"):
        return SmtpTestResult(success=False, message="SMTP is disabled. Enable it first.")

    from email.mime.text import MIMEText

    msg = MIMEText(
        "This is a test email from QA Insight AI to verify your SMTP configuration.",
        "plain",
    )
    msg["Subject"] = "QA Insight AI — SMTP Test"
    msg["From"] = cfg.get("from_address", "noreply@qainsight.io")
    msg["To"] = current_user.email

    try:
        await aiosmtplib.send(
            msg,
            hostname=cfg.get("host", "localhost"),
            port=int(cfg.get("port", 587)),
            username=cfg.get("user") or None,
            password=cfg.get("password") or None,
            use_tls=bool(cfg.get("tls", True)),
            start_tls=not bool(cfg.get("tls", True)),
        )
        logger.info("SMTP test email sent to %s", current_user.email)
        return SmtpTestResult(success=True, message=f"Test email sent to {current_user.email}")
    except Exception:
        logger.exception("SMTP test failed")
        return SmtpTestResult(
            success=False,
            message="Failed to send test email. Please verify the SMTP configuration and try again.",
        )
