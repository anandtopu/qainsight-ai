"""
Unit tests for user management endpoints.
All DB calls and heavy dependencies (bcrypt, jose) are mocked.

Strategy: stub only the uninstalled native deps (bcrypt, jose) and the
app.core.security / app.core.deps modules at the sys.modules level so
the full import chain can resolve without Docker.
"""
from __future__ import annotations

import hashlib
import sys
import types
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_stub(name: str, **attrs) -> types.ModuleType:
    """Create and register a lightweight stub module."""
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# Only stub packages that are NOT installed in the local venv.
# sqlalchemy, fastapi, pydantic ARE installed — do not stub them.

if "bcrypt" not in sys.modules:
    _make_stub(
        "bcrypt",
        checkpw=MagicMock(return_value=True),
        hashpw=MagicMock(return_value=b"$2b$fake"),
        gensalt=MagicMock(return_value=b"$2b$12$salt"),
    )

if "jose" not in sys.modules:
    _jose_jwt = _make_stub("jose.jwt", encode=MagicMock(return_value="tok"), decode=MagicMock(return_value={}))
    _make_stub("jose", jwt=_jose_jwt, JWTError=Exception)

# Stub only the app.core modules that pull in bcrypt/jose
if "app.core.security" not in sys.modules:
    _make_stub(
        "app.core.security",
        verify_password=MagicMock(return_value=True),
        get_password_hash=MagicMock(return_value="hashed_pw"),
        create_access_token=MagicMock(return_value="access_token"),
        create_refresh_token=MagicMock(return_value="refresh_token"),
        decode_token=MagicMock(return_value={"sub": str(uuid.uuid4()), "type": "access"}),
    )

if "app.core.deps" not in sys.modules:
    _make_stub(
        "app.core.deps",
        require_role=MagicMock(return_value=MagicMock()),
        get_current_active_user=MagicMock(),
        verify_webhook_secret=MagicMock(),
        require_project_role=MagicMock(return_value=MagicMock()),
    )

# Stub DB connection factories (no real DB in unit tests)
if "app.db.postgres" not in sys.modules:
    from sqlalchemy.orm import DeclarativeBase
    class _Base(DeclarativeBase): pass
    _make_stub("app.db.postgres", get_db=MagicMock(), AsyncSession=MagicMock(), Base=_Base)
if "app.db.mongo" not in sys.modules:
    _make_stub("app.db.mongo", get_mongo_db=MagicMock(), close_mongo=MagicMock())
if "app.db.redis_client" not in sys.modules:
    _make_stub("app.db.redis_client", get_redis=MagicMock(), close_redis=MagicMock())

# ── Now safe to import app modules ────────────────────────────────────────────

from app.models.postgres import UserRole  # noqa: E402
from app.models.schemas import (  # noqa: E402
    AdminCreateUserRequest,
    ApiKeyCreate,
    InviteUserRequest,
)


# ── Helpers ────────────────────────────────────────────────────

def _make_user(role: UserRole = UserRole.QA_ENGINEER, is_active: bool = True) -> MagicMock:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.email = "test@example.com"
    u.username = "testuser"
    u.full_name = "Test User"
    u.role = role
    u.is_active = is_active
    u.hashed_password = "hashed"
    u.created_at = datetime.now(timezone.utc)
    return u


def _execute_result(scalar_value=None, all_value=None) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = scalar_value
    r.scalars.return_value.all.return_value = all_value or []
    return r


# ── Schema validation ──────────────────────────────────────────

class TestAdminCreateUserRequest:
    def test_valid_payload(self):
        req = AdminCreateUserRequest(
            email="newuser@example.com",
            username="newuser",
            role=UserRole.QA_ENGINEER,
        )
        assert req.email == "newuser@example.com"
        assert req.username == "newuser"
        assert req.role == UserRole.QA_ENGINEER
        assert req.full_name is None

    def test_username_too_short_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AdminCreateUserRequest(email="x@x.com", username="ab")

    def test_username_too_long_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AdminCreateUserRequest(email="x@x.com", username="a" * 51)

    def test_invalid_email_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AdminCreateUserRequest(email="not-an-email", username="validuser")

    def test_full_name_optional(self):
        req = AdminCreateUserRequest(
            email="u@example.com",
            username="myuser",
            full_name="Jane Doe",
        )
        assert req.full_name == "Jane Doe"

    def test_default_role_is_qa_engineer(self):
        req = AdminCreateUserRequest(email="u@example.com", username="usr123")
        assert req.role == UserRole.QA_ENGINEER


# ── AdminCreateUser endpoint ───────────────────────────────────

class TestAdminCreateUser:
    @pytest.mark.asyncio
    async def test_happy_path_returns_temp_password(self):
        """Admin creates a new user; response includes a non-empty temp password."""
        from app.routers.users import admin_create_user

        admin = _make_user(role=UserRole.ADMIN)
        user_id = uuid.uuid4()
        created_at = datetime.now(timezone.utc)

        db = AsyncMock()
        db.execute.return_value = _execute_result(scalar_value=None)

        # Simulate DB refresh: set PK and server-default fields on the ORM object
        async def _refresh(obj):
            obj.id = user_id
            obj.is_active = True
            obj.created_at = created_at

        db.refresh = AsyncMock(side_effect=_refresh)

        payload = AdminCreateUserRequest(
            email="new@example.com",
            username="newuser",
            role=UserRole.QA_ENGINEER,
        )

        with patch("app.routers.users.get_password_hash", return_value="hashed_temp"):
            result = await admin_create_user(payload=payload, db=db, current_user=admin)

        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        assert result.temp_password
        assert len(result.temp_password) >= 8
        assert result.email == "new@example.com"
        assert result.username == "newuser"

    @pytest.mark.asyncio
    async def test_duplicate_email_or_username_raises_409(self):
        from fastapi import HTTPException
        from app.routers.users import admin_create_user

        admin = _make_user(role=UserRole.ADMIN)
        existing = _make_user()

        db = AsyncMock()
        db.execute.return_value = _execute_result(scalar_value=existing)

        payload = AdminCreateUserRequest(email="existing@example.com", username="existing")

        with pytest.raises(HTTPException) as exc_info:
            await admin_create_user(payload=payload, db=db, current_user=admin)

        assert exc_info.value.status_code == 409

    def test_temp_passwords_are_unique(self):
        import secrets
        passwords = {secrets.token_urlsafe(12) for _ in range(30)}
        assert len(passwords) == 30


# ── list_api_keys endpoint ─────────────────────────────────────

class TestListApiKeys:
    @pytest.mark.asyncio
    async def test_returns_active_keys_for_current_user(self):
        from app.routers.api_keys import list_api_keys

        user = _make_user()
        key = MagicMock()
        key.id = uuid.uuid4()
        key.name = "CI Key"
        key.key_hint = "qai_abc123..."
        key.scopes = ["test:read"]
        key.is_active = True
        key.expires_at = None
        key.last_used_at = None
        key.created_at = datetime.now(timezone.utc)

        db = AsyncMock()
        db.execute.return_value = _execute_result(all_value=[key])

        result = await list_api_keys(db=db, current_user=user)
        assert result == [key]

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_keys(self):
        from app.routers.api_keys import list_api_keys

        user = _make_user()
        db = AsyncMock()
        db.execute.return_value = _execute_result(all_value=[])

        result = await list_api_keys(db=db, current_user=user)
        assert result == []


# ── create_api_key endpoint ────────────────────────────────────

class TestCreateApiKey:
    @pytest.mark.asyncio
    async def test_raw_key_starts_with_qai_prefix(self):
        from app.routers.api_keys import create_api_key

        user = _make_user()
        new_key = MagicMock()
        new_key.id = uuid.uuid4()
        new_key.name = "Test Key"
        new_key.key_hint = "qai_test12..."
        new_key.scopes = []
        new_key.is_active = True
        new_key.expires_at = None
        new_key.last_used_at = None
        new_key.created_at = datetime.now(timezone.utc)

        db = AsyncMock()
        db.refresh = AsyncMock()

        payload = ApiKeyCreate(name="Test Key", scopes=[])

        with patch("app.routers.api_keys.ApiKey", return_value=new_key):
            result = await create_api_key(payload=payload, db=db, current_user=user)

        assert result.raw_key.startswith("qai_")
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    def test_hash_function_uses_sha256(self):
        from app.routers.api_keys import _hash_key
        raw = "qai_mysecrettoken"
        assert _hash_key(raw) == hashlib.sha256(raw.encode()).hexdigest()

    def test_raw_key_not_stored_plaintext(self):
        from app.routers.api_keys import _hash_key
        raw = "qai_mysecrettoken"
        assert _hash_key(raw) != raw


# ── invite_user endpoint ───────────────────────────────────────

class TestInviteUser:
    @pytest.mark.asyncio
    async def test_creates_invitation_with_register_link(self):
        from app.routers.users import invite_user

        admin = _make_user(role=UserRole.ADMIN)
        inv_id = uuid.uuid4()

        db = AsyncMock()
        db.execute.return_value = _execute_result(scalar_value=None)

        # Simulate DB refresh: set the PK that the DB would normally assign
        async def _refresh(obj):
            obj.id = inv_id

        db.refresh = AsyncMock(side_effect=_refresh)

        payload = InviteUserRequest(email="newbie@example.com")

        result = await invite_user(payload=payload, db=db, current_user=admin)

        assert "register" in result.invitation_link
        assert "newbie@example.com" in result.invitation_link
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rejects_already_registered_email(self):
        from fastapi import HTTPException
        from app.routers.users import invite_user

        admin = _make_user(role=UserRole.ADMIN)
        existing_user = _make_user()

        db = AsyncMock()
        db.execute.return_value = _execute_result(scalar_value=existing_user)

        payload = InviteUserRequest(email="existing@example.com")

        with pytest.raises(HTTPException) as exc_info:
            await invite_user(payload=payload, db=db, current_user=admin)

        assert exc_info.value.status_code == 409
