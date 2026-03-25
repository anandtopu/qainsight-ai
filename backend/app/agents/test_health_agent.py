"""
Test Health Agent.
Analyzes test code quality for AUTOMATION_DEFECT failures.
Detects anti-patterns: hardcoded waits, empty catch blocks, brittle selectors, missing assertions.
"""
import logging
import re

from app.agents.base import BaseAgent
from app.db.postgres import AsyncSessionLocal
from app.models.postgres import TestCase

logger = logging.getLogger("agents.test_health")

_ANTIPATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"Thread\.sleep\s*\(|time\.sleep\s*\(", re.I),
     "warning", "Hardcoded sleep detected — use explicit waits or polling instead"),
    (re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}", re.S),
     "critical", "Empty catch block swallows exceptions — failures may be silently ignored"),
    (re.compile(r"@Ignore|@pytest\.mark\.skip|@Disabled", re.I),
     "info", "Test is suppressed/ignored — verify this is intentional"),
    (re.compile(r'By\.xpath\s*\(\s*["\'][^"\']*\d{3,}[^"\']*["\']', re.I),
     "warning", "XPath with long numeric index — brittle, breaks on DOM changes"),
    (re.compile(r"static\s+(?:volatile\s+)?(?:final\s+)?\w+\s+\w+\s*=", re.I),
     "info", "Static mutable field in test class — potential shared state between tests"),
]


def _analyze_source(source_code: str) -> list[dict]:
    violations = []
    for pattern, severity, description in _ANTIPATTERNS:
        matches = pattern.findall(source_code)
        if matches:
            violations.append({
                "pattern": description,
                "severity": severity,
                "occurrences": len(matches),
            })

    has_assertions = bool(re.search(r"assert|expect\(|should\.", source_code, re.I))
    if source_code.strip() and not has_assertions:
        violations.append({
            "pattern": "No assertions found — test may pass vacuously",
            "severity": "critical",
            "occurrences": 1,
        })

    return violations


class TestHealthAgent(BaseAgent):
    stage_name = "test_health"

    async def run(self, state: dict) -> dict:
        pipeline_run_id: str = state["pipeline_run_id"]
        project_id: str = state["project_id"]
        analyses: dict = state.get("analyses", {})

        await self.mark_stage_running(pipeline_run_id)
        await self.broadcast_progress(project_id, {"status": "running", "message": "Analyzing test code health..."})

        automation_test_ids = [
            tc_id for tc_id, a in analyses.items()
            if a.get("failure_category") == "AUTOMATION_DEFECT"
        ]

        if not automation_test_ids:
            await self.mark_stage_done(pipeline_run_id, result_data={"analyzed": 0})
            return {"test_health_findings": []}

        findings = []
        for tc_id in automation_test_ids[:15]:
            finding = await self._analyze_test(tc_id)
            if finding:
                findings.append(finding)

        await self.mark_stage_done(
            pipeline_run_id,
            result_data={"analyzed": len(findings), "with_violations": sum(1 for f in findings if f.get("violations"))},
        )
        await self.broadcast_progress(project_id, {
            "status": "completed",
            "message": f"Test health analyzed {len(findings)} automation defects",
        })

        return {"test_health_findings": findings}

    async def _analyze_test(self, tc_id: str) -> dict | None:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(select(TestCase).where(TestCase.id == tc_id))
            tc = result.scalar_one_or_none()
            if not tc:
                return None

        source_code = tc.error_message or ""

        violations = _analyze_source(source_code)
        critical_count = sum(1 for v in violations if v["severity"] == "critical")
        warning_count = sum(1 for v in violations if v["severity"] == "warning")

        if critical_count > 0:
            health_score = max(0, 40 - critical_count * 10)
            recommendation = "CRITICAL: Test has automation defects requiring immediate fix before re-running."
        elif warning_count > 0:
            health_score = max(40, 80 - warning_count * 10)
            recommendation = f"WARNING: {warning_count} test anti-pattern(s) detected. Refactor to improve reliability."
        else:
            health_score = 90
            recommendation = "Test code appears healthy. Failure may be due to environment or test data issues."

        return {
            "test_case_id": tc_id,
            "test_name": tc.test_name,
            "health_score": health_score,
            "violations": violations,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "recommendation": recommendation,
        }
