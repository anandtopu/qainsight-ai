"""
Test Summary Agent — Stage 4 of the offline pipeline.

Aggregates outputs from the anomaly-detection and root-cause-analysis stages,
then uses an LLM to generate:
  • A 2-3 sentence executive summary
  • A full markdown report stored in MongoDB[run_summaries]
"""
import logging
from datetime import datetime, timezone

from app.agents.base import BaseAgent
from app.db.mongo import Collections, get_mongo_db
from app.services.llm_factory import get_llm

logger = logging.getLogger("agents.summary")


_SYSTEM_PROMPT = """\
You are a QA Engineering Lead writing a concise post-run analysis report.
Be factual, direct, and actionable. Focus on failures and risks.
Do not pad the report. Use plain markdown.
"""


class SummaryAgent(BaseAgent):
    stage_name = "summary"

    async def run(self, state: dict) -> dict:
        pipeline_run_id = state["pipeline_run_id"]
        test_run_id = state["test_run_id"]
        project_id = state["project_id"]

        await self.mark_stage_running(pipeline_run_id)
        await self.broadcast_progress(
            project_id,
            {"status": "running", "message": "Generating test run summary…"},
        )

        try:
            run_data = state.get("test_run_data") or {}
            anomalies = state.get("anomalies") or []
            analyses = state.get("analyses") or {}
            anomaly_summary = state.get("anomaly_summary") or ""

            executive_summary, markdown_report = await self._generate_report(
                run_data=run_data,
                anomaly_summary=anomaly_summary,
                anomalies=anomalies,
                analyses=analyses,
            )

            # Persist to MongoDB
            await self._store_summary(test_run_id, executive_summary, markdown_report, state)

            await self.mark_stage_done(
                pipeline_run_id,
                result_data={"summary_length": len(markdown_report)},
            )
            await self.broadcast_progress(
                project_id,
                {"status": "completed", "message": "Test run summary generated"},
            )

            return {
                "executive_summary": executive_summary,
                "summary_markdown": markdown_report,
                "completed_stages": ["summary"],
                "errors": [],
                "current_stage": "triage",
            }

        except Exception as exc:
            error_msg = f"Summary agent error: {exc}"
            logger.error(error_msg, exc_info=True)
            await self.mark_stage_done(pipeline_run_id, error=error_msg)
            return {
                "executive_summary": None,
                "summary_markdown": None,
                "errors": [error_msg],
                "completed_stages": ["summary"],
                "current_stage": "triage",
            }

    async def _generate_report(
        self,
        run_data: dict,
        anomaly_summary: str,
        anomalies: list[dict],
        analyses: dict[str, dict],
    ) -> tuple[str, str]:
        """Call LLM to generate both the executive summary and full markdown report."""
        pass_rate = run_data.get("pass_rate", 0)
        total = run_data.get("total_tests", 0)
        failed = run_data.get("failed_tests", 0)
        build = run_data.get("build_number", "?")
        branch = run_data.get("branch", "?")

        # Collect top analysis findings
        analysis_bullets = []
        for tc_id, analysis in list(analyses.items())[:10]:
            if analysis.get("confidence_score", 0) >= 50:
                analysis_bullets.append(
                    f"- **{analysis.get('failure_category', 'UNKNOWN')}** "
                    f"(confidence {analysis.get('confidence_score', 0)}%): "
                    f"{analysis.get('root_cause_summary', '')[:200]}"
                )

        context = (
            f"Build: {build} | Branch: {branch}\n"
            f"Results: {total} tests, {failed} failures, {pass_rate:.1f}% pass rate\n\n"
            f"Anomalies:\n{anomaly_summary or 'None detected.'}\n\n"
            f"Top failure root causes:\n" + ("\n".join(analysis_bullets) or "No analyses available.")
        )

        exec_prompt = (
            f"{_SYSTEM_PROMPT}\n\n"
            f"Write a 2-3 sentence executive summary for this test run:\n{context}"
        )
        report_prompt = (
            f"{_SYSTEM_PROMPT}\n\n"
            f"Write a complete markdown test run report with sections for:\n"
            f"## Overview\n## Key Findings\n## Failure Analysis\n## Recommended Actions\n\n"
            f"Data:\n{context}"
        )

        llm = get_llm()
        exec_resp = await llm.ainvoke(exec_prompt)
        report_resp = await llm.ainvoke(report_prompt)

        executive_summary = (
            exec_resp.content if hasattr(exec_resp, "content") else str(exec_resp)
        ).strip()
        markdown_report = (
            report_resp.content if hasattr(report_resp, "content") else str(report_resp)
        ).strip()

        return executive_summary, markdown_report

    async def _store_summary(
        self,
        test_run_id: str,
        executive_summary: str,
        markdown_report: str,
        state: dict,
    ) -> None:
        db = get_mongo_db()
        await db[Collections.RUN_SUMMARIES].update_one(
            {"test_run_id": test_run_id},
            {
                "$set": {
                    "test_run_id": test_run_id,
                    "project_id": state.get("project_id"),
                    "build_number": state.get("build_number"),
                    "executive_summary": executive_summary,
                    "markdown_report": markdown_report,
                    "anomaly_count": len(state.get("anomalies") or []),
                    "is_regression": state.get("is_regression", False),
                    "analysis_count": len(state.get("analyses") or {}),
                    "generated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
