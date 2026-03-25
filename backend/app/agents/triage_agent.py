"""
Defect Triage Agent — Stage 5 of the offline pipeline.

For each analysed failure with confidence >= threshold:
  1. Deduplicates against existing open Jira tickets
  2. Creates a new ticket (or skips if one already exists)
  3. Updates the Defect table

Returns a list of triage actions taken.
"""
import logging

from sqlalchemy import select

from app.agents.base import BaseAgent
from app.core.config import settings
from app.db.postgres import AsyncSessionLocal
from app.models.postgres import Defect, TestCase
from app.services.jira_client import create_jira_issue

logger = logging.getLogger("agents.triage")

# Only auto-triage when confidence is high enough
_AUTO_TRIAGE_CONFIDENCE = settings.AI_CONFIDENCE_THRESHOLD
# Categories that always get a ticket (even at lower confidence)
_HIGH_PRIORITY_CATEGORIES = {"PRODUCT_BUG", "INFRASTRUCTURE"}


class DefectTriageAgent(BaseAgent):
    stage_name = "triage"

    async def run(self, state: dict) -> dict:
        pipeline_run_id = state["pipeline_run_id"]
        project_id = state["project_id"]
        analyses = state.get("analyses") or {}
        test_run_data = state.get("test_run_data") or {}

        await self.mark_stage_running(pipeline_run_id)
        await self.broadcast_progress(
            project_id,
            {"status": "running", "message": "Triaging defects and creating tickets…"},
        )

        triage_results: list[dict] = []
        errors: list[str] = []

        for tc_id, analysis in analyses.items():
            confidence = analysis.get("confidence_score", 0)
            category = analysis.get("failure_category", "UNKNOWN")

            # Determine if this failure warrants a ticket
            should_triage = (
                (confidence >= _AUTO_TRIAGE_CONFIDENCE) or
                (category in _HIGH_PRIORITY_CATEGORIES and confidence >= 50)
            ) and not analysis.get("is_flaky", False)

            if not should_triage:
                triage_results.append({
                    "test_case_id": tc_id,
                    "action": "skipped",
                    "reason": f"confidence={confidence} / category={category} / flaky={analysis.get('is_flaky')}",
                })
                continue

            try:
                result = await self._triage_one(tc_id, analysis, project_id, test_run_data, state)
                triage_results.append(result)
            except Exception as exc:
                err = f"Triage failed for {tc_id}: {exc}"
                logger.error(err, exc_info=True)
                errors.append(err)
                triage_results.append({"test_case_id": tc_id, "action": "error", "error": str(exc)})

        created = sum(1 for r in triage_results if r["action"] == "created")
        skipped = sum(1 for r in triage_results if r["action"] == "skipped")

        await self.mark_stage_done(
            pipeline_run_id,
            result_data={"created": created, "skipped": skipped, "errors": len(errors)},
        )
        await self.broadcast_progress(
            project_id,
            {
                "status": "completed",
                "message": f"Triage complete: {created} ticket(s) created, {skipped} skipped",
            },
        )

        return {
            "triage_results": triage_results,
            "completed_stages": ["triage"],
            "errors": errors,
            "current_stage": "done",
        }

    async def _triage_one(
        self,
        tc_id: str,
        analysis: dict,
        project_id: str,
        test_run_data: dict,
        state: dict,
    ) -> dict:
        """Create or skip a Jira ticket for one failed test case."""
        async with AsyncSessionLocal() as db:
            # Look up test case name and project key
            tc_result = await db.execute(
                select(TestCase.test_name, TestCase.suite_name).where(TestCase.id == tc_id)
            )
            tc = tc_result.first()
            test_name = tc.test_name if tc else tc_id

            # Check for existing open defect
            existing = await db.execute(
                select(Defect).where(
                    Defect.test_case_id == tc_id,
                    Defect.resolution_status == "OPEN",
                )
            )
            if existing.scalar_one_or_none():
                return {"test_case_id": tc_id, "action": "existing", "reason": "Open defect already tracked"}

        # Create Jira ticket if integration is enabled
        ticket_key = ticket_url = ticket_id = None
        if settings.JIRA_ENABLED:
            try:
                jira_project_key = await self._get_jira_key(project_id)
                ticket = await create_jira_issue(
                    project_key=jira_project_key or settings.JIRA_DEFAULT_PROJECT_KEY,
                    test_name=test_name,
                    run_id=state["test_run_id"],
                    ai_summary=analysis.get("root_cause_summary", ""),
                    recommended_action=", ".join(analysis.get("recommended_actions", [])[:2]),
                    stack_trace="",  # Fetched by Jira client from MongoDB if needed
                    dashboard_link=f"/runs/{state['test_run_id']}",
                )
                ticket_id = ticket.get("ticket_id")
                ticket_key = ticket.get("ticket_key")
                ticket_url = ticket.get("ticket_url")
            except Exception as jira_exc:
                logger.warning("Jira ticket creation skipped: %s", jira_exc)

        # Persist Defect record
        async with AsyncSessionLocal() as db:
            defect = Defect(
                test_case_id=tc_id,
                project_id=project_id,
                jira_ticket_id=ticket_id,
                jira_ticket_url=ticket_url,
                jira_status="Open" if ticket_key else None,
                ai_confidence_score=analysis.get("confidence_score"),
                failure_category=analysis.get("failure_category", "UNKNOWN"),
                resolution_status="OPEN",
            )
            db.add(defect)
            await db.commit()

        return {
            "test_case_id": tc_id,
            "action": "created",
            "ticket_key": ticket_key,
            "ticket_url": ticket_url,
        }

    async def _get_jira_key(self, project_id: str) -> str | None:
        from app.models.postgres import Project
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Project.jira_project_key).where(Project.id == project_id))
            row = result.first()
            return row.jira_project_key if row else None
