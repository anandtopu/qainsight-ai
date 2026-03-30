"""User management endpoints — list, invite, role updates, project members."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user, require_role
from app.core.security import get_password_hash
from app.db.postgres import get_db
from app.models.postgres import Project, ProjectMember, User, UserInvitation, UserRole
from app.models.schemas import (
    AddProjectMemberRequest,
    AdminCreateUserRequest,
    AdminCreateUserResponse,
    InviteUserRequest,
    InviteUserResponse,
    ProjectMemberResponse,
    UpdateProjectMemberRoleRequest,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
    UserListResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["User Management"])
projects_router = APIRouter(prefix="/api/v1/projects", tags=["User Management"])


# ── User CRUD ────────────────────────────────────────────────

@router.get("", response_model=list[UserListResponse])
async def list_users(
    is_active: Optional[bool] = Query(None),
    role: Optional[UserRole] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.QA_LEAD)),
):
    """List all users. Requires QA_LEAD or higher."""
    stmt = select(User).order_by(User.full_name)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    if role is not None:
        stmt = stmt.where(User.role == role)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{user_id}", response_model=UserListResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.QA_LEAD)),
):
    """Get a specific user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}/role", response_model=UserListResponse)
async def update_user_role(
    user_id: uuid.UUID,
    payload: UpdateUserRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Update a user's global role. Requires ADMIN."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role")
    user.role = payload.role
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}/status", response_model=UserListResponse)
async def update_user_status(
    user_id: uuid.UUID,
    payload: UpdateUserStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Activate or deactivate a user account. Requires ADMIN."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")
    user.is_active = payload.is_active
    await db.commit()
    await db.refresh(user)
    return user


@router.post("", response_model=AdminCreateUserResponse, status_code=201)
async def admin_create_user(
    payload: AdminCreateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Admin creates a user directly with a temporary password. Requires ADMIN."""
    existing = await db.execute(
        select(User).where(
            (User.email == payload.email) | (User.username == payload.username)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username already registered",
        )

    temp_password = secrets.token_urlsafe(12)
    logger.info("admin_creating_user", email=payload.email, role=str(payload.role), by=str(current_user.id))
    user = User(
        email=payload.email,
        username=payload.username,
        full_name=payload.full_name,
        hashed_password=get_password_hash(temp_password),
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return AdminCreateUserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        temp_password=temp_password,
    )


@router.post("/invite", response_model=InviteUserResponse, status_code=201)
async def invite_user(
    payload: InviteUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Invite a user by email with a specified role. Requires ADMIN."""
    # Check if email already registered
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    # Check for existing unexpired invite
    existing_invite = await db.execute(
        select(UserInvitation).where(
            UserInvitation.email == payload.email,
            UserInvitation.is_used == False,  # noqa: E712
            UserInvitation.expires_at > datetime.now(timezone.utc),
        )
    )
    if existing_invite.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active invitation already exists for this email",
        )

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    invitation = UserInvitation(
        email=payload.email,
        role=payload.role,
        token=token,
        invited_by_id=current_user.id,
        expires_at=expires_at,
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    # In production this would send an email — for now return the link
    invitation_link = f"/register?token={token}&email={payload.email}"

    return InviteUserResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        invitation_link=invitation_link,
    )


# ── Project Members ───────────────────────────────────────────

@projects_router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
async def list_project_members(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all members of a project."""
    # Verify project exists
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    result = await db.execute(
        select(ProjectMember, User)
        .join(User, ProjectMember.user_id == User.id)
        .where(ProjectMember.project_id == project_id)
        .order_by(User.full_name)
    )
    rows = result.all()

    return [
        ProjectMemberResponse(
            id=member.id,
            user_id=member.user_id,
            project_id=member.project_id,
            role=member.role,
            created_at=member.created_at,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
        )
        for member, user in rows
    ]


@projects_router.post("/{project_id}/members", response_model=ProjectMemberResponse, status_code=201)
async def add_project_member(
    project_id: uuid.UUID,
    payload: AddProjectMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.QA_LEAD)),
):
    """Add a user to a project with a role. Requires QA_LEAD or higher."""
    # Verify project
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Verify user
    user_result = await db.execute(select(User).where(User.id == payload.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Check not already a member
    existing = await db.execute(
        select(ProjectMember).where(
            ProjectMember.user_id == payload.user_id,
            ProjectMember.project_id == project_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this project",
        )

    logger.info("adding_project_member", project_id=str(project_id), user_id=str(payload.user_id), role=str(payload.role), by=str(current_user.id))
    member = ProjectMember(user_id=payload.user_id, project_id=project_id, role=payload.role)
    db.add(member)
    await db.commit()
    await db.refresh(member)

    return ProjectMemberResponse(
        id=member.id,
        user_id=member.user_id,
        project_id=member.project_id,
        role=member.role,
        created_at=member.created_at,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
    )


@projects_router.patch("/{project_id}/members/{user_id}", response_model=ProjectMemberResponse)
async def update_project_member_role(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: UpdateProjectMemberRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.QA_LEAD)),
):
    """Update a project member's role. Requires QA_LEAD or higher."""
    result = await db.execute(
        select(ProjectMember, User)
        .join(User, ProjectMember.user_id == User.id)
        .where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project membership not found")

    member, user = row
    member.role = payload.role
    await db.commit()
    await db.refresh(member)

    return ProjectMemberResponse(
        id=member.id,
        user_id=member.user_id,
        project_id=member.project_id,
        role=member.role,
        created_at=member.created_at,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
    )


@projects_router.delete("/{project_id}/members/{user_id}", status_code=204)
async def remove_project_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Remove a user from a project. Requires ADMIN."""
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project membership not found")
    await db.delete(member)
    await db.commit()
    return None