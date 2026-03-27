"""Unit tests for AnalysisAgent fallback and per-test analysis behavior."""
import asyncio
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("asyncpg")

from app.agents.analysis_agent import AnalysisAgent


class TestAnalysisAgentFallbacks:
    def test_build_timeout_analysis_sets_expected_flags(self):
        agent = AnalysisAgent()

        result = agent._build_timeout_analysis()

        assert result["failure_category"] == agent.UNKNOWN_CATEGORY
        assert result["timed_out"] is True
        assert result["requires_human_review"] is True
        assert result["confidence_score"] == 0

    def test_build_error_analysis_includes_error_message(self):
        agent = AnalysisAgent()

        result = agent._build_error_analysis(RuntimeError("llm offline"))

        assert result["failure_category"] == agent.UNKNOWN_CATEGORY
        assert result["requires_human_review"] is True
        assert result["error"] == "llm offline"
        assert "Analysis failed" in result["root_cause_summary"]


class TestAnalysisAgentAnalyzeOne:
    @pytest.mark.asyncio
    async def test_analyse_one_returns_timeout_fallback(self, monkeypatch):
        agent = AnalysisAgent()
        agent._upsert_analysis = AsyncMock()  # type: ignore[method-assign]

        async def _raise_timeout(*_args, **_kwargs):
            raise asyncio.TimeoutError

        monkeypatch.setattr("app.agents.analysis_agent.run_triage_agent", _raise_timeout)

        result = await agent._analyse_one(
            asyncio.Semaphore(1),
            "tc-1",
            {"test_name": "test_login"},
            {"test_run_data": {}},
        )

        assert result["timed_out"] is True
        assert result["failure_category"] == agent.UNKNOWN_CATEGORY
        agent._upsert_analysis.assert_awaited_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_analyse_one_returns_error_fallback_on_exception(self, monkeypatch):
        agent = AnalysisAgent()
        agent._upsert_analysis = AsyncMock()  # type: ignore[method-assign]

        async def _raise_error(*_args, **_kwargs):
            raise RuntimeError("provider failure")

        monkeypatch.setattr("app.agents.analysis_agent.run_triage_agent", _raise_error)

        result = await agent._analyse_one(
            asyncio.Semaphore(1),
            "tc-2",
            {"test_name": "test_checkout"},
            {"test_run_data": {}},
        )

        assert result["failure_category"] == agent.UNKNOWN_CATEGORY
        assert result["error"] == "provider failure"
        agent._upsert_analysis.assert_awaited_once()  # type: ignore[attr-defined]
