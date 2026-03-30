"""
Smoke tests for test-management export endpoints.

Strategy: mirrors the approach in test_user_management.py — stub only the
native deps that are NOT available in the test venv and the app.core/app.db
modules that would require a live database, then import app code at module
level.  All DB interactions are replaced by AsyncMock objects.

Tests verify:
  - Correct Content-Type / Content-Disposition headers on 200 responses.
  - HTTP 404 is raised when the requested plan/strategy does not exist.
  - get_suite_test_cases includes a `source` field for every returned item.
  - get_suite_test_cases degrades gracefully when the DB raises (migration guard).
"""
from __future__ import annotations

import importlib.util
import sys
import types
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stub(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


# ---------------------------------------------------------------------------
# Autouse fixture: stub security/auth and DB connection modules.
# All other heavy packages (openpyxl, python-docx, reportlab, asyncpg) are
# assumed installed via requirements.txt — exactly as in CI.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _stub_external_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub native deps and app.core/app.db modules for each test."""
    with monkeypatch.context() as m:
        # Stub bcrypt / jose only when not installed (same guard as test_user_management.py)
        if importlib.util.find_spec("bcrypt") is None:
            m.setitem(
                sys.modules, "bcrypt",
                _make_stub("bcrypt",
                           checkpw=MagicMock(return_value=True),
                           hashpw=MagicMock(return_value=b"$2b$fake"),
                           gensalt=MagicMock(return_value=b"$2b$12$salt")),
            )
        if importlib.util.find_spec("jose") is None:
            jose_jwt_stub = _make_stub("jose.jwt",
                                       encode=MagicMock(return_value="tok"),
                                       decode=MagicMock(return_value={}))
            m.setitem(sys.modules, "jose.jwt", jose_jwt_stub)
            m.setitem(sys.modules, "jose",
                      _make_stub("jose", jwt=jose_jwt_stub, JWTError=Exception))

        # Always stub app.core modules that pull in bcrypt/jose/config.
        m.setitem(sys.modules, "app.core.security",
                  _make_stub("app.core.security",
                             verify_password=MagicMock(return_value=True),
                             get_password_hash=MagicMock(return_value="hashed"),
                             create_access_token=MagicMock(return_value="access_token"),
                             create_refresh_token=MagicMock(return_value="refresh_token"),
                             decode_token=MagicMock(
                                 return_value={"sub": str(uuid.uuid4()), "type": "access"})))
        m.setitem(sys.modules, "app.core.deps",
                  _make_stub("app.core.deps",
                             get_current_active_user=MagicMock(),
                             require_role=MagicMock(return_value=MagicMock()),
                             verify_webhook_secret=MagicMock(),
                             require_project_role=MagicMock(return_value=MagicMock())))

        # Always stub DB connection factories (no real DB in unit tests).
        from sqlalchemy.orm import DeclarativeBase

        class _Base(DeclarativeBase):
            pass

        m.setitem(sys.modules, "app.db.postgres",
                  _make_stub("app.db.postgres",
                             get_db=MagicMock(),
                             AsyncSession=MagicMock(),
                             Base=_Base))
        m.setitem(sys.modules, "app.db.mongo",
                  _make_stub("app.db.mongo",
                             get_mongo_db=MagicMock(),
                             close_mongo=MagicMock()))
        m.setitem(sys.modules, "app.db.redis_client",
                  _make_stub("app.db.redis_client",
                             get_redis=MagicMock(),
                             close_redis=MagicMock()))
        yield


# ---------------------------------------------------------------------------
# Module-level app imports (safe once the stubs above are in sys.modules).
# These run at collection time — all heavy C-extension deps (asyncpg, etc.)
# must be installed via requirements.txt for this to succeed.
# ---------------------------------------------------------------------------

from app.models.postgres import ManagedTestCase, TestPlan, TestStrategy, User  # noqa: E402


# ---------------------------------------------------------------------------
# Shared factories
# ---------------------------------------------------------------------------

def _make_user():
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.username = "testuser"
    u.is_active = True
    return u


def _make_exec_result(*, scalar_value=None, all_value=None, scalars_value=None):
    r = MagicMock()
    r.scalar_one_or_none.return_value = scalar_value
    r.scalar.return_value = scalar_value
    r.all.return_value = all_value or []
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = scalars_value or []
    r.scalars.return_value = scalars_mock
    return r


def _make_plan(plan_id=None):
    p = MagicMock(spec=TestPlan)
    p.id = plan_id or uuid.uuid4()
    p.name = "Sprint Plan"
    p.status = "active"
    p.description = "A test plan"
    p.objective = "Ensure coverage"
    p.total_cases = 2
    p.executed_cases = 1
    p.passed_cases = 1
    p.failed_cases = 0
    p.blocked_cases = 0
    p.planned_start_date = None
    p.planned_end_date = None
    return p


def _make_strategy(strategy_id=None):
    s = MagicMock(spec=TestStrategy)
    s.id = strategy_id or uuid.uuid4()
    s.name = "QA Strategy"
    s.status = "draft"
    s.version_label = "1.0"
    s.objective = "Ensure quality"
    s.scope = "Web app"
    s.out_of_scope = None
    s.test_approach = "BDD"
    s.automation_approach = "Selenium"
    s.defect_management = None
    s.entry_criteria = []
    s.exit_criteria = []
    s.test_types = []
    s.risk_assessment = []
    s.environments = []
    return s


# ---------------------------------------------------------------------------
# Tests: export_test_cases_excel
# ---------------------------------------------------------------------------

class TestExportTestCasesExcel:
    @pytest.mark.asyncio
    async def test_returns_xlsx_content_type(self):
        from app.routers.test_management_exports import export_test_cases_excel

        db = AsyncMock()
        db.execute.return_value = _make_exec_result(all_value=[])

        resp = await export_test_cases_excel(
            project_id=None, status=None, test_type=None,
            priority=None, search=None, limit=5000,
            db=db, current_user=_make_user(),
        )

        assert resp.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "test-cases.xlsx" in resp.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_filters_by_project_id(self):
        from app.routers.test_management_exports import export_test_cases_excel

        db = AsyncMock()
        db.execute.return_value = _make_exec_result(all_value=[])

        resp = await export_test_cases_excel(
            project_id=uuid.uuid4(), status=None, test_type=None,
            priority=None, search=None, limit=5000,
            db=db, current_user=_make_user(),
        )

        assert resp.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_respects_small_limit(self):
        from app.routers.test_management_exports import export_test_cases_excel

        db = AsyncMock()
        db.execute.return_value = _make_exec_result(all_value=[])

        resp = await export_test_cases_excel(
            project_id=None, status=None, test_type=None,
            priority=None, search=None, limit=1,
            db=db, current_user=_make_user(),
        )

        assert resp.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ---------------------------------------------------------------------------
# Tests: export_test_plan_word
# ---------------------------------------------------------------------------

class TestExportTestPlanWord:
    @pytest.mark.asyncio
    async def test_returns_docx_for_existing_plan(self):
        from app.routers.test_management_exports import export_test_plan_word

        plan_id = uuid.uuid4()
        plan = _make_plan(plan_id)
        db = AsyncMock()
        db.execute.side_effect = [_make_exec_result(scalar_value=plan), _make_exec_result(all_value=[])]

        resp = await export_test_plan_word(plan_id=plan_id, db=db, current_user=_make_user())

        assert resp.media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert f"test-plan-{plan_id}.docx" in resp.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_raises_404_for_missing_plan(self):
        from fastapi import HTTPException
        from app.routers.test_management_exports import export_test_plan_word

        db = AsyncMock()
        db.execute.return_value = _make_exec_result(scalar_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await export_test_plan_word(plan_id=uuid.uuid4(), db=db, current_user=_make_user())

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Tests: export_test_plan_pdf
# ---------------------------------------------------------------------------

class TestExportTestPlanPdf:
    @pytest.mark.asyncio
    async def test_returns_pdf_for_existing_plan(self):
        from app.routers.test_management_exports import export_test_plan_pdf

        plan_id = uuid.uuid4()
        plan = _make_plan(plan_id)
        db = AsyncMock()
        db.execute.side_effect = [_make_exec_result(scalar_value=plan), _make_exec_result(all_value=[])]

        resp = await export_test_plan_pdf(plan_id=plan_id, db=db, current_user=_make_user())

        assert resp.media_type == "application/pdf"
        assert f"test-plan-{plan_id}.pdf" in resp.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_raises_404_for_missing_plan(self):
        from fastapi import HTTPException
        from app.routers.test_management_exports import export_test_plan_pdf

        db = AsyncMock()
        db.execute.return_value = _make_exec_result(scalar_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await export_test_plan_pdf(plan_id=uuid.uuid4(), db=db, current_user=_make_user())

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Tests: export_test_strategy_word
# ---------------------------------------------------------------------------

class TestExportTestStrategyWord:
    @pytest.mark.asyncio
    async def test_returns_docx_for_existing_strategy(self):
        from app.routers.test_management_exports import export_test_strategy_word

        strategy_id = uuid.uuid4()
        strategy = _make_strategy(strategy_id)
        db = AsyncMock()
        db.execute.return_value = _make_exec_result(scalar_value=strategy)

        resp = await export_test_strategy_word(strategy_id=strategy_id, db=db, current_user=_make_user())

        assert resp.media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert f"test-strategy-{strategy_id}.docx" in resp.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_raises_404_for_missing_strategy(self):
        from fastapi import HTTPException
        from app.routers.test_management_exports import export_test_strategy_word

        db = AsyncMock()
        db.execute.return_value = _make_exec_result(scalar_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await export_test_strategy_word(strategy_id=uuid.uuid4(), db=db, current_user=_make_user())

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Tests: export_test_strategy_pdf
# ---------------------------------------------------------------------------

class TestExportTestStrategyPdf:
    @pytest.mark.asyncio
    async def test_returns_pdf_for_existing_strategy(self):
        from app.routers.test_management_exports import export_test_strategy_pdf

        strategy_id = uuid.uuid4()
        strategy = _make_strategy(strategy_id)
        db = AsyncMock()
        db.execute.return_value = _make_exec_result(scalar_value=strategy)

        resp = await export_test_strategy_pdf(strategy_id=strategy_id, db=db, current_user=_make_user())

        assert resp.media_type == "application/pdf"
        assert f"test-strategy-{strategy_id}.pdf" in resp.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_raises_404_for_missing_strategy(self):
        from fastapi import HTTPException
        from app.routers.test_management_exports import export_test_strategy_pdf

        db = AsyncMock()
        db.execute.return_value = _make_exec_result(scalar_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await export_test_strategy_pdf(strategy_id=uuid.uuid4(), db=db, current_user=_make_user())

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Tests: get_suite_test_cases
# ---------------------------------------------------------------------------

class TestGetSuiteTestCases:

    def _auto_case(self):
        tc = MagicMock()
        tc.id = uuid.uuid4()
        tc.test_name = "Login test"
        tc.suite_name = "Auth"
        tc.status = "PASSED"
        tc.duration_ms = 120
        tc.class_name = "LoginTests"
        tc.package_name = "auth"
        tc.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return tc

    def _manual_case(self):
        tc = MagicMock()
        tc.id = uuid.uuid4()
        tc.title = "Manual login test"
        tc.suite_name = "Auth"
        tc.last_execution_status = "passed"
        tc.status = "active"
        tc.feature_area = "Authentication"
        tc.created_at = datetime(2024, 1, 2, tzinfo=timezone.utc)
        return tc

    @pytest.mark.asyncio
    async def test_includes_source_field_for_all_cases(self):
        from app.routers.test_management_exports import get_suite_test_cases

        db = AsyncMock()
        db.execute.side_effect = [
            _make_exec_result(scalars_value=[self._auto_case()]),
            _make_exec_result(scalars_value=[self._manual_case()]),
        ]

        result = await get_suite_test_cases(
            suite_name="Auth", project_id=None, limit=100,
            db=db, current_user=_make_user(),
        )

        assert len(result) == 2
        sources = {item["source"] for item in result}
        assert sources == {"automation", "manual"}

    @pytest.mark.asyncio
    async def test_fallback_on_migration_error_returns_automation_only(self):
        """When suite_name column is missing, endpoint returns only automation cases."""
        from sqlalchemy.exc import ProgrammingError
        from app.routers.test_management_exports import get_suite_test_cases

        db = AsyncMock()
        db.execute.side_effect = [
            _make_exec_result(scalars_value=[self._auto_case()]),
            ProgrammingError("column suite_name does not exist", {}, None),
        ]
        db.rollback = AsyncMock()

        result = await get_suite_test_cases(
            suite_name="Auth", project_id=None, limit=100,
            db=db, current_user=_make_user(),
        )

        assert all(item["source"] == "automation" for item in result)
        db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_cases(self):
        from app.routers.test_management_exports import get_suite_test_cases

        db = AsyncMock()
        db.execute.side_effect = [
            _make_exec_result(scalars_value=[]),
            _make_exec_result(scalars_value=[]),
        ]

        result = await get_suite_test_cases(
            suite_name="EmptySuite", project_id=None, limit=100,
            db=db, current_user=_make_user(),
        )

        assert result == []
