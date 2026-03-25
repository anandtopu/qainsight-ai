"""
Flaky Sentinel Agent.
Investigates the full lifecycle of flaky tests: when flakiness started,
what changed, and whether quarantine is warranted.
"""
import json
import logging

from app.agents.base import BaseAgent
from app.db.postgres import AsyncSessionLocal
from app.models.postgres import TestCase, TestCaseHistory, TestStatus
from app.tools.fetch_build_changes import fetch_build_changes

logger = logging.getLogger("agents.flaky_sentinel")


class FlakySentinelAgent(BaseAgent):
    stage_name = "flaky_sentinel"

    async def run(self, state: dict) -> dict:
        pipeline_run_id: str = state["pipeline_run_id"]
        project_id: str = state["project_id"]
        analyses: dict = state.get("analyses", {})

        await self.mark_stage_running(pipeline_run_id)
        await self.broadcast_progress(project_id, {"status": "running", "message": "Investigating flaky test lifecycles..."})

        # Identify tests classified as FLAKY
        flaky_test_ids = [
            tc_id for tc_id, analysis in analyses.items()
            if analysis.get("is_flaky") or analysis.get("failure_category") == "FLAKY"
        ]

        if not flaky_test_ids:
            await self.mark_stage_done(pipeline_run_id, result_data={"flaky_investigated": 0})
            return {"flaky_findings": []}

        findings = []
        async with AsyncSessionLocal() as db:
            for tc_id in flaky_test_ids[:10]:  # Cap at 10 to avoid excessive processing
                finding = await self._investigate_flaky_test(db, tc_id, project_id)
                if finding:
                    findings.append(finding)

        await self.mark_stage_done(pipeline_run_id, result_data={"flaky_investigated": len(findings)})
        await self.broadcast_progress(project_id, {
            "status": "completed",
            "message": f"Flaky sentinel investigated {len(findings)} tests",
        })

        return {"flaky_findings": findings}

    async def _investigate_flaky_test(self, db, tc_id: str, project_id: str) -> dict | None:
        from sqlalchemy import select
        # Get test case details
        result = await db.execute(select(TestCase).where(TestCase.id == tc_id))
        tc = result.scalar_one_or_none()
        if not tc:
            return None

        # Get last 20 history entries
        hist_result = await db.execute(
            select(TestCaseHistory)
            .where(TestCaseHistory.test_fingerprint == tc.test_fingerprint)
            .order_by(TestCaseHistory.created_at.desc())
            .limit(20)
        )
        history = hist_result.scalars().all()

        if len(history) < 3:
            return {
                "test_case_id": tc_id,
                "test_name": tc.test_name,
                "flaky_since": "insufficient history",
                "recommendation": "MONITOR — insufficient history to determine onset",
            }

        # Find flakiness onset: first run where it started alternating
        statuses = [h.status for h in reversed(history)]  # oldest first
        build_numbers = []
        async with AsyncSessionLocal() as db2:
            from app.models.postgres import TestRun
            for h in reversed(history):
                run_result = await db2.execute(
                    select(TestRun.build_number).where(TestRun.id == h.test_run_id)
                )
                build_number = run_result.scalar_one_or_none()
                build_numbers.append(build_number or "unknown")

        onset_index = 0
        for i in range(1, len(statuses)):
            if statuses[i] != statuses[i - 1]:
                onset_index = i
                break

        flaky_since_build = build_numbers[onset_index] if onset_index < len(build_numbers) else "unknown"
        last_stable_build = build_numbers[onset_index - 1] if onset_index > 0 else "unknown"

        # Compute failure rate
        failed_count = sum(1 for s in statuses if s in (TestStatus.FAILED, TestStatus.BROKEN))
        failure_rate = failed_count / len(statuses)

        # Fetch build changes around onset
        change_summary = "Build change lookup skipped."
        if flaky_since_build != "unknown" and last_stable_build != "unknown":
            try:
                changes_json = await fetch_build_changes.ainvoke({
                    "params_json": json.dumps({
                        "test_fingerprint": tc.test_fingerprint,
                        "stable_build_number": last_stable_build,
                        "flaky_build_number": flaky_since_build,
                        "project_id": project_id,
                    })
                })
                changes = json.loads(changes_json)
                change_summary = changes.get("change_summary", "No changes found.")
            except Exception as exc:
                logger.debug("Build changes fetch failed: %s", exc)

        # Quarantine recommendation
        if failure_rate > 0.5:
            recommendation = "QUARANTINE — failing more than 50% of the time, blocking CI reliability"
        elif failure_rate > 0.25:
            recommendation = "INVESTIGATE URGENTLY — high flakiness rate, significant noise source"
        else:
            recommendation = "MONITOR — low flakiness rate, worth tracking but not yet critical"

        return {
            "test_case_id": tc_id,
            "test_name": tc.test_name,
            "test_fingerprint": tc.test_fingerprint,
            "failure_rate": round(failure_rate, 3),
            "history_length": len(statuses),
            "flaky_since_build": flaky_since_build,
            "last_stable_build": last_stable_build,
            "change_summary": change_summary,
            "recommendation": recommendation,
            "status_history": [str(s) for s in statuses[-10:]],
        }
