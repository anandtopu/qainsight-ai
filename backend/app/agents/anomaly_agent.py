"""
Anomaly Detection Agent — Stage 2 of the offline pipeline.

Compares the current test run against historical baselines to detect:
  - Pass-rate regressions
  - New failures (tests that previously passed)
  - Performance anomalies (duration spikes)
  - Flaky test patterns

Uses an LLM to synthesise findings into a short human-readable summary.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select

from app.agents.base import BaseAgent
from app.db.postgres import AsyncSessionLocal
from app.models.postgres import TestCase, TestCaseHistory, TestRun
from app.services.llm_factory import get_llm

logger = logging.getLogger("agents.anomaly")

_REGRESSION_THRESHOLD = 10.0       # % drop in pass rate vs. baseline
_PERF_SPIKE_MULTIPLIER = 2.0       # duration > 2× average is a spike
_MIN_HISTORY_RUNS = 3               # Need at least this many prior runs for regression check
_FLAKY_WINDOW_RUNS = 10             # Look back 10 runs for flakiness


class AnomalyDetectionAgent(BaseAgent):
    stage_name = "anomaly_detection"

    async def run(self, state: dict) -> dict:
        pipeline_run_id = state["pipeline_run_id"]
        test_run_id = state["test_run_id"]
        project_id = state["project_id"]
        current_pass_rate = state.get("pass_rate", 0.0)

        await self.mark_stage_running(pipeline_run_id)
        await self.broadcast_progress(
            project_id,
            {"status": "running", "message": "Scanning for anomalies and regressions…"},
        )

        anomalies: list[dict] = []
        is_regression = False
        regression_tests: list[str] = []

        try:
            # ── 1. Pass-rate regression ────────────────────────────
            baseline_rate, prior_run_ids = await self._get_baseline_pass_rate(project_id, test_run_id)
            if baseline_rate is not None and prior_run_ids:
                drop = baseline_rate - current_pass_rate
                if drop >= _REGRESSION_THRESHOLD:
                    is_regression = True
                    anomalies.append({
                        "type": "pass_rate_regression",
                        "severity": "HIGH" if drop >= 20 else "MEDIUM",
                        "description": (
                            f"Pass rate dropped {drop:.1f}% (from {baseline_rate:.1f}% to {current_pass_rate:.1f}%)"
                        ),
                        "value": drop,
                    })

            # ── 2. New failures (tests that passed last run) ───────
            if prior_run_ids:
                new_failures = await self._find_new_failures(test_run_id, prior_run_ids[-1])
                if new_failures:
                    regression_tests = [str(tc_id) for tc_id in new_failures]
                    anomalies.append({
                        "type": "new_failures",
                        "severity": "HIGH",
                        "description": f"{len(new_failures)} test(s) failed for the first time this run",
                        "test_ids": regression_tests,
                    })

            # ── 3. Performance anomalies ───────────────────────────
            perf_anomalies = await self._detect_perf_anomalies(test_run_id, project_id)
            anomalies.extend(perf_anomalies)

            # ── 4. Flaky tests in this run ─────────────────────────
            flaky_in_run = await self._find_flaky_tests_in_run(test_run_id)
            if flaky_in_run:
                anomalies.append({
                    "type": "flaky_tests",
                    "severity": "LOW",
                    "description": f"{len(flaky_in_run)} known-flaky test(s) failed — may not indicate real regressions",
                    "test_ids": [str(t) for t in flaky_in_run],
                })

            # ── 5. LLM summary of findings ─────────────────────────
            anomaly_summary = await self._generate_summary(anomalies, current_pass_rate, state.get("total_tests", 0))

            await self.mark_stage_done(
                pipeline_run_id,
                result_data={"anomaly_count": len(anomalies), "is_regression": is_regression},
            )
            await self.broadcast_progress(
                project_id,
                {
                    "status": "completed",
                    "message": f"Anomaly detection complete: {len(anomalies)} finding(s)",
                    "is_regression": is_regression,
                },
            )

            return {
                "anomalies": anomalies,
                "is_regression": is_regression,
                "regression_tests": regression_tests,
                "anomaly_summary": anomaly_summary,
                "completed_stages": ["anomaly_detection"],
                "errors": [],
                "current_stage": "root_cause_analysis",
            }

        except Exception as exc:
            error_msg = f"Anomaly agent error: {exc}"
            logger.error(error_msg, exc_info=True)
            await self.mark_stage_done(pipeline_run_id, error=error_msg)
            return {
                "anomalies": [],
                "is_regression": False,
                "regression_tests": [],
                "anomaly_summary": None,
                "errors": [error_msg],
                "completed_stages": ["anomaly_detection"],
                "current_stage": "root_cause_analysis",
            }

    # ── Private helpers ────────────────────────────────────────────

    async def _get_baseline_pass_rate(
        self, project_id: str, current_run_id: str
    ) -> tuple[Optional[float], list[str]]:
        """Average pass rate over the last N completed runs (excluding current)."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TestRun.id, TestRun.pass_rate)
                .where(
                    TestRun.project_id == project_id,
                    TestRun.id != current_run_id,
                    TestRun.pass_rate.is_not(None),
                )
                .order_by(TestRun.created_at.desc())
                .limit(_MIN_HISTORY_RUNS)
            )
            rows = result.all()
            if len(rows) < _MIN_HISTORY_RUNS:
                return None, []
            rates = [r.pass_rate for r in rows]
            return sum(rates) / len(rates), [str(r.id) for r in rows]

    async def _find_new_failures(self, current_run_id: str, previous_run_id: str) -> list:
        """Tests that FAILED in current run but PASSED in the previous run."""
        async with AsyncSessionLocal() as db:
            # Current run failures
            cur = await db.execute(
                select(TestCase.test_fingerprint)
                .where(
                    TestCase.test_run_id == current_run_id,
                    TestCase.status.in_(["FAILED", "BROKEN"]),
                )
            )
            current_failures = {r.test_fingerprint for r in cur.all()}

            if not current_failures:
                return []

            # Previous run — same fingerprints that were PASSED
            prev = await db.execute(
                select(TestCase.id)
                .where(
                    TestCase.test_run_id == previous_run_id,
                    TestCase.test_fingerprint.in_(current_failures),
                    TestCase.status == "PASSED",
                )
            )
            return [r.id for r in prev.all()]

    async def _detect_perf_anomalies(self, test_run_id: str, project_id: str) -> list[dict]:
        """Find tests where duration is > 2× their historical average."""
        async with AsyncSessionLocal() as db:
            # Average duration per fingerprint over last 30 days
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            hist = await db.execute(
                select(
                    TestCaseHistory.test_fingerprint,
                    func.avg(TestCaseHistory.duration_ms).label("avg_ms"),
                )
                .where(TestCaseHistory.created_at >= cutoff)
                .group_by(TestCaseHistory.test_fingerprint)
            )
            avg_by_fingerprint = {r.test_fingerprint: float(r.avg_ms) for r in hist.all()}

            if not avg_by_fingerprint:
                return []

            # Current run durations
            cur = await db.execute(
                select(TestCase.test_fingerprint, TestCase.duration_ms, TestCase.test_name)
                .where(
                    TestCase.test_run_id == test_run_id,
                    TestCase.duration_ms.is_not(None),
                )
            )
            spikes = []
            for row in cur.all():
                avg = avg_by_fingerprint.get(row.test_fingerprint)
                if avg and avg > 0 and row.duration_ms > avg * _PERF_SPIKE_MULTIPLIER:
                    spikes.append(row.test_name)

            if spikes:
                return [{
                    "type": "performance_spike",
                    "severity": "MEDIUM",
                    "description": f"{len(spikes)} test(s) ran >2× slower than usual",
                    "tests": spikes[:10],
                }]
            return []

    async def _find_flaky_tests_in_run(self, test_run_id: str) -> list:
        """Tests in this run that have a historical flakiness pattern."""
        async with AsyncSessionLocal() as db:
            # Get failed tests in this run
            failed = await db.execute(
                select(TestCase.test_fingerprint, TestCase.id)
                .where(
                    TestCase.test_run_id == test_run_id,
                    TestCase.status.in_(["FAILED", "BROKEN"]),
                )
            )
            failed_rows = failed.all()
            if not failed_rows:
                return []

            # Check history for flaky pattern
            flaky_ids = []
            for row in failed_rows:
                hist = await db.execute(
                    select(TestCaseHistory.status)
                    .where(TestCaseHistory.test_fingerprint == row.test_fingerprint)
                    .order_by(TestCaseHistory.created_at.desc())
                    .limit(_FLAKY_WINDOW_RUNS)
                )
                statuses = [r.status for r in hist.all()]
                if len(statuses) >= 4:
                    fail_count = sum(1 for s in statuses if s in ("FAILED", "BROKEN"))
                    fail_rate = fail_count / len(statuses)
                    if 0.1 <= fail_rate <= 0.9:
                        flaky_ids.append(row.id)

            return flaky_ids

    async def _generate_summary(
        self, anomalies: list[dict], pass_rate: float, total_tests: int
    ) -> str:
        """Use LLM to write a concise anomaly summary."""
        if not anomalies:
            return f"No anomalies detected. Pass rate: {pass_rate:.1f}% across {total_tests} tests."

        descriptions = "\n".join(f"- {a['description']}" for a in anomalies)
        prompt = (
            f"Summarise these test anomalies in 2-3 sentences for an engineering team:\n"
            f"Pass rate: {pass_rate:.1f}%\nTotal tests: {total_tests}\n"
            f"Findings:\n{descriptions}"
        )
        try:
            llm = get_llm()
            response = await llm.ainvoke(prompt)
            _raw = response.content if hasattr(response, "content") else str(response)
            return _raw if isinstance(_raw, str) else str(_raw)
        except Exception:
            return descriptions
