"""
Root Cause Analysis Agent — Stage 3 of the offline pipeline.

For each failed test, runs the LangChain ReAct triage agent concurrently
(bounded by a semaphore to avoid LLM overload), then persists results to
the ai_analysis PostgreSQL table.

This agent wraps the existing run_triage_agent() from services/agent.py
so the single-test analysis path is unchanged.
"""
import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.agents.base import BaseAgent
from app.core.config import settings
from app.db.postgres import AsyncSessionLocal
from app.models.postgres import AIAnalysis, TestCase
from app.services.agent import run_triage_agent

logger = logging.getLogger("agents.analysis")


class AnalysisAgent(BaseAgent):
    stage_name = "root_cause_analysis"

    async def run(self, state: dict) -> dict:
        pipeline_run_id = state["pipeline_run_id"]
        project_id = state["project_id"]
        failed_ids: list[str] = state.get("failed_test_ids", [])

        await self.mark_stage_running(pipeline_run_id)
        await self.broadcast_progress(
            project_id,
            {
                "status": "running",
                "message": f"Running root-cause analysis on {len(failed_ids)} failed test(s)…",
            },
        )

        if not failed_ids:
            await self.mark_stage_done(pipeline_run_id, result_data={"analysed": 0})
            return {
                "analyses": {},
                "completed_stages": ["root_cause_analysis"],
                "errors": [],
                "current_stage": "summary",
            }

        # Fetch test metadata once
        test_meta = await self._fetch_test_metadata(failed_ids)

        semaphore = asyncio.Semaphore(settings.LLM_MAX_CONCURRENT_ANALYSES)
        tasks = [
            self._analyse_one(semaphore, tc_id, test_meta.get(tc_id, {}), state)
            for tc_id in failed_ids
        ]

        try:
            results_list = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as gather_exc:
            # Shouldn't happen with return_exceptions=True, but guard against it
            logger.error("asyncio.gather failed unexpectedly: %s", gather_exc)
            results_list = [gather_exc] * len(failed_ids)

        analyses: dict[str, dict] = {}
        errors: list[str] = []
        timed_out = 0
        for tc_id, result in zip(failed_ids, results_list):
            if isinstance(result, BaseException):
                errors.append(f"Analysis failed for {tc_id}: {result}")
                analyses[tc_id] = {"error": str(result), "confidence_score": 0}
            else:
                analyses[tc_id] = result
                if result.get("timed_out"):
                    timed_out += 1

        await self.mark_stage_done(
            pipeline_run_id,
            result_data={
                "analysed": len(analyses),
                "errors": len(errors),
                "timed_out": timed_out,
            },
        )
        await self.broadcast_progress(
            project_id,
            {
                "status": "completed",
                "message": f"Root-cause analysis complete: {len(analyses)} test(s) analysed"
                + (f", {timed_out} timed out" if timed_out else ""),
            },
        )

        return {
            "analyses": analyses,
            "completed_stages": ["root_cause_analysis"],
            "errors": errors,
            "current_stage": "summary",
        }

    async def _analyse_one(
        self,
        semaphore: asyncio.Semaphore,
        tc_id: str,
        meta: dict,
        state: dict,
    ) -> dict:
        async with semaphore:
            logger.info("Analysing test case %s: %s", tc_id, meta.get("test_name", ""))
            try:
                analysis = await asyncio.wait_for(
                    run_triage_agent(
                        test_case_id=tc_id,
                        test_name=meta.get("test_name", tc_id),
                        service_name=meta.get("suite_name"),
                        timestamp=None,
                        ocp_pod_name=state.get("test_run_data", {}).get("ocp_pod_name"),
                        ocp_namespace=state.get("test_run_data", {}).get("ocp_namespace"),
                    ),
                    timeout=settings.AI_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "ReAct agent timed out after %ds for test %s — using fallback",
                    settings.AI_TIMEOUT_SECONDS, tc_id,
                )
                analysis = {
                    "root_cause_summary": f"Analysis timed out after {settings.AI_TIMEOUT_SECONDS}s. Manual review required.",
                    "failure_category": "UNKNOWN",
                    "backend_error_found": False,
                    "pod_issue_found": False,
                    "is_flaky": False,
                    "confidence_score": 0,
                    "recommended_actions": ["Re-run analysis with a faster LLM or higher timeout", "Review stack trace manually"],
                    "evidence_references": [],
                    "requires_human_review": True,
                    "timed_out": True,
                }
            except Exception as exc:
                logger.error("ReAct agent failed for %s: %s", tc_id, exc)
                analysis = {
                    "root_cause_summary": f"Analysis failed: {exc}. Manual review required.",
                    "failure_category": "UNKNOWN",
                    "backend_error_found": False,
                    "pod_issue_found": False,
                    "is_flaky": False,
                    "confidence_score": 0,
                    "recommended_actions": ["Review stack trace manually", "Check LLM service connectivity"],
                    "evidence_references": [],
                    "requires_human_review": True,
                    "error": str(exc),
                }

            # Persist to ai_analysis table (best-effort — don't fail the stage if upsert fails)
            try:
                await self._upsert_analysis(tc_id, analysis)
            except Exception as db_exc:
                logger.error("Failed to persist analysis for %s: %s", tc_id, db_exc)

            return analysis

    async def _fetch_test_metadata(self, tc_ids: list[str]) -> dict[str, dict]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TestCase.id, TestCase.test_name, TestCase.suite_name, TestCase.class_name)
                .where(TestCase.id.in_(tc_ids))
            )
            return {
                str(row.id): {
                    "test_name": row.test_name,
                    "suite_name": row.suite_name,
                    "class_name": row.class_name,
                }
                for row in result.all()
            }

    async def _upsert_analysis(self, tc_id: str, analysis: dict) -> None:
        """Insert or update ai_analysis row for this test case."""
        async with AsyncSessionLocal() as db:
            stmt = pg_insert(AIAnalysis).values(
                test_case_id=tc_id,
                root_cause_summary=analysis.get("root_cause_summary"),
                failure_category=analysis.get("failure_category", "UNKNOWN"),
                backend_error_found=analysis.get("backend_error_found", False),
                pod_issue_found=analysis.get("pod_issue_found", False),
                is_flaky=analysis.get("is_flaky", False),
                confidence_score=analysis.get("confidence_score", 0),
                recommended_actions=analysis.get("recommended_actions", []),
                evidence_references=analysis.get("evidence_references", []),
                llm_provider=analysis.get("llm_provider"),
                llm_model=analysis.get("llm_model"),
                requires_human_review=analysis.get("requires_human_review", True),
                created_at=datetime.now(timezone.utc),
            ).on_conflict_do_update(
                index_elements=["test_case_id"],
                set_={
                    "root_cause_summary": analysis.get("root_cause_summary"),
                    "failure_category": analysis.get("failure_category", "UNKNOWN"),
                    "backend_error_found": analysis.get("backend_error_found", False),
                    "pod_issue_found": analysis.get("pod_issue_found", False),
                    "is_flaky": analysis.get("is_flaky", False),
                    "confidence_score": analysis.get("confidence_score", 0),
                    "recommended_actions": analysis.get("recommended_actions", []),
                    "evidence_references": analysis.get("evidence_references", []),
                    "requires_human_review": analysis.get("requires_human_review", True),
                },
            )
            await db.execute(stmt)
            await db.commit()
