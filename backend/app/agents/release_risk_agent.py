"""
Release Risk Agent (Stage 6).
Produces a structured go/no-go release recommendation based on full pipeline results.
"""
import json
import logging
import re

from app.agents.base import BaseAgent
from app.core.config import settings
from app.db.postgres import AsyncSessionLocal
from app.models.postgres import Defect, FailureCategory, ReleaseDecision
from app.services.llm_factory import get_llm

logger = logging.getLogger("agents.release_risk")

_RISK_PROMPT = """You are a QA release gate analyst. Given the following test run summary, produce a release recommendation.

Test Run Summary:
{summary}

Failure Analysis:
{failures}

Anomalies:
{anomalies}

Open Defects: {open_defects}

Evaluate:
1. Is the pass rate acceptable for release? (threshold: {pass_rate_threshold}%)
2. Are there PRODUCT_BUG failures that would affect end users?
3. Are there infrastructure issues that may persist in production?
4. What are the blocking issues?

Respond ONLY with a JSON object:
{{
  "recommendation": "GO" | "NO_GO" | "CONDITIONAL_GO",
  "risk_score": <integer 0-100>,
  "blocking_issues": ["<issue1>", "<issue2>"],
  "conditions_for_go": ["<condition1>"],
  "reasoning": "<2-3 sentence explanation>"
}}"""


class ReleaseRiskAgent(BaseAgent):
    stage_name = "release_risk"

    async def run(self, state: dict) -> dict:
        pipeline_run_id: str = state["pipeline_run_id"]
        project_id: str = state["project_id"]
        test_run_id: str = state["test_run_id"]

        await self.mark_stage_running(pipeline_run_id)
        await self.broadcast_progress(project_id, {"status": "running", "message": "Evaluating release readiness..."})

        try:
            decision = await self._evaluate(state)
        except Exception as exc:
            logger.error("Release risk evaluation failed: %s", exc, exc_info=True)
            decision = {
                "recommendation": "CONDITIONAL_GO",
                "risk_score": 50,
                "blocking_issues": [],
                "conditions_for_go": ["Manual review required — automated assessment failed"],
                "reasoning": f"Release risk agent encountered an error: {exc}",
            }

        await self._persist_decision(test_run_id, decision)

        await self.mark_stage_done(
            pipeline_run_id,
            result_data={
                "recommendation": decision["recommendation"],
                "risk_score": decision["risk_score"],
            },
        )
        await self.broadcast_progress(project_id, {
            "status": "completed",
            "recommendation": decision["recommendation"],
            "risk_score": decision["risk_score"],
        })

        return {"release_decision": decision}

    async def _evaluate(self, state: dict) -> dict:
        analyses = state.get("analyses", {})
        anomaly_summary = state.get("anomaly_summary", "No anomalies detected.")
        executive_summary = state.get("executive_summary", "")
        pass_rate = state.get("pass_rate", 0.0)

        open_defects = 0
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, func as sa_func
            result = await db.execute(
                select(sa_func.count(Defect.id))
                .where(Defect.project_id == state["project_id"])
                .where(Defect.resolution_status == "OPEN")
            )
            open_defects = result.scalar() or 0

        threshold = settings.RELEASE_PASS_RATE_THRESHOLD

        if pass_rate < threshold * 0.7:
            product_bugs = [
                a for a in analyses.values()
                if a.get("failure_category") == FailureCategory.PRODUCT_BUG
                and not a.get("is_flaky")
            ]
            return {
                "recommendation": "NO_GO",
                "risk_score": max(95 - int(pass_rate), 60),
                "blocking_issues": [
                    f"Pass rate {pass_rate:.1f}% is far below threshold {threshold:.1f}%",
                    *([f"{len(product_bugs)} confirmed product bugs"] if product_bugs else []),
                    *(["Open defect count: " + str(open_defects)] if open_defects > 5 else []),
                ],
                "conditions_for_go": [],
                "reasoning": (
                    f"Pass rate of {pass_rate:.1f}% is critically below the {threshold:.1f}% threshold. "
                    f"Found {len(product_bugs)} PRODUCT_BUG failures. This release is not ready."
                ),
            }

        failure_lines = []
        for tc_id, a in list(analyses.items())[:15]:
            cat = a.get("failure_category", "UNKNOWN")
            conf = a.get("confidence_score", 0)
            summary = a.get("root_cause_summary", "")[:150]
            failure_lines.append(f"- [{cat}] conf={conf}% {summary}")

        prompt = _RISK_PROMPT.format(
            summary=executive_summary or f"Pass rate: {pass_rate:.1f}%, total analyses: {len(analyses)}",
            failures="\n".join(failure_lines) if failure_lines else "No failures",
            anomalies=anomaly_summary or "None",
            open_defects=open_defects,
            pass_rate_threshold=threshold,
        )

        llm = get_llm(temperature=0.0)
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            try:
                decision = json.loads(json_match.group())
                decision.setdefault("recommendation", "CONDITIONAL_GO")
                decision.setdefault("risk_score", 50)
                decision.setdefault("blocking_issues", [])
                decision.setdefault("conditions_for_go", [])
                decision.setdefault("reasoning", "")
                return decision
            except json.JSONDecodeError:
                pass

        product_bugs = sum(
            1 for a in analyses.values()
            if a.get("failure_category") == FailureCategory.PRODUCT_BUG and not a.get("is_flaky")
        )
        risk_score = max(0, min(100, int((1 - pass_rate / 100) * 80 + product_bugs * 5)))
        return {
            "recommendation": "GO" if pass_rate >= threshold and product_bugs == 0 else "CONDITIONAL_GO",
            "risk_score": risk_score,
            "blocking_issues": [f"{product_bugs} confirmed product bugs"] if product_bugs > 0 else [],
            "conditions_for_go": ["Resolve product bugs before deploying"] if product_bugs > 0 else [],
            "reasoning": f"Pass rate: {pass_rate:.1f}%, product bugs: {product_bugs}, open defects: {open_defects}",
        }

    async def _persist_decision(self, test_run_id: str, decision: dict) -> None:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            existing = await db.execute(
                select(ReleaseDecision).where(ReleaseDecision.test_run_id == test_run_id)
            )
            record = existing.scalar_one_or_none()
            if record:
                record.recommendation = decision["recommendation"]
                record.risk_score = decision["risk_score"]
                record.blocking_issues = decision.get("blocking_issues", [])
                record.conditions_for_go = decision.get("conditions_for_go", [])
                record.reasoning = decision.get("reasoning", "")
            else:
                db.add(ReleaseDecision(
                    test_run_id=test_run_id,
                    recommendation=decision["recommendation"],
                    risk_score=decision["risk_score"],
                    blocking_issues=decision.get("blocking_issues", []),
                    conditions_for_go=decision.get("conditions_for_go", []),
                    reasoning=decision.get("reasoning", ""),
                ))
            await db.commit()
