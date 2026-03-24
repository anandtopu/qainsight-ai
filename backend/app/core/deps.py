"""Dependencies for FastAPI (authentication, authorisation, webhook security)."""
import logging
import uuid
from typing import Callable

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError  # type: ignore
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_token
from app.db.postgres import get_db
from app.models.postgres import User, UserRole

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    scheme_name="JWT",
)

# Role hierarchy — higher index = more privileged
_ROLE_ORDER: list[UserRole] = [
    UserRole.VIEWER,
    UserRole.TESTER,
    UserRole.QA_ENGINEER,
    UserRole.QA_LEAD,
    UserRole.ADMIN,
]


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    """Validate JWT access token and return the matching User row."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type — use an access token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise credentials_exception

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the current user, raising 403 if the account is disabled."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return current_user


def require_role(min_role: UserRole) -> Callable:
    """
    Return a FastAPI dependency that enforces a minimum role level.

    Usage:
        @router.post("", dependencies=[Depends(require_role(UserRole.QA_LEAD))])
        # or
        current_user: User = Depends(require_role(UserRole.QA_ENGINEER))
    """
    min_idx = _ROLE_ORDER.index(min_role)

    async def _check(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        try:
            user_idx = _ROLE_ORDER.index(current_user.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        if user_idx < min_idx:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least {min_role.value} role",
            )
        return current_user

    return _check


async def verify_webhook_secret(
    x_webhook_secret: str = Header(..., alias="X-Webhook-Secret"),
) -> None:
    """Validate the shared webhook secret header sent by MinIO."""
    if x_webhook_secret != settings.WEBHOOK_SECRET:
        logger.warning("Webhook request with invalid secret rejected")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook secret",
        )
