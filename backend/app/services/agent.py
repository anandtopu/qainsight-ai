"""
LangChain ReAct agent service.
Runs a Thought → Action → Observation loop using 5 investigation tools
to produce a structured root-cause analysis for any test failure.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate

from app.core.config import settings
from app.db.mongo import Collections, get_mongo_db
from app.services.llm_factory import get_llm
from app.tools.analyze_ocp import analyze_openshift_pod_events
from app.tools.check_flakiness import check_test_flakiness
from app.tools.fetch_rest_payload import fetch_rest_api_payload
from app.tools.fetch_stacktrace import fetch_allure_stacktrace
from app.tools.query_splunk import query_splunk_logs

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Software Quality Assurance Architect and Site Reliability Engineer.
Your objective is to analyse failed automated test cases, identify the root cause, and produce
a clear, structured, actionable defect analysis.

You have access to five investigation tools:
{tools}

STRICT RULES:
1. Base ALL conclusions strictly on data returned by your tools. NEVER guess or hallucinate root causes.
2. If tool responses are empty or inconclusive, state: "Insufficient telemetry to determine root cause."
3. Always check for infrastructure/environment issues BEFORE assuming the application code is broken.
4. Check for flakiness history before classifying a failure as a product bug.
5. You MUST use at least the stack trace tool before forming any conclusion.

After completing your investigation, return ONLY a valid JSON object with this exact schema:
{{
  "root_cause_summary": "string (2-4 sentences explaining the root cause in plain English)",
  "failure_category": "PRODUCT_BUG | INFRASTRUCTURE | TEST_DATA | AUTOMATION_DEFECT | FLAKY",
  "backend_error_found": true | false,
  "pod_issue_found": true | false,
  "is_flaky": true | false,
  "confidence_score": integer 0-100,
  "recommended_actions": ["action 1", "action 2", "action 3"],
  "evidence_references": [
    {{"source": "stacktrace | splunk | ocp_events | flakiness", "reference_id": "...", "excerpt": "..."}}
  ]
}}

Available tools: {tool_names}

Use the following format:
Thought: your reasoning about what to investigate next
Action: the tool name to use
Action Input: the input to the tool
Observation: the tool's output
... (repeat Thought/Action/Observation as needed)
Thought: I now have enough information to form a conclusion
Final Answer: {{valid JSON object as specified above}}

Begin!

Question: {input}
Thought: {agent_scratchpad}"""


def _get_tools():
    return [
        fetch_allure_stacktrace,
        fetch_rest_api_payload,
        query_splunk_logs,
        check_test_flakiness,
        analyze_openshift_pod_events,
    ]


async def run_triage_agent(
    test_case_id: str,
    test_name: str,
    service_name: Optional[str] = None,
    timestamp: Optional[str] = None,
    ocp_pod_name: Optional[str] = None,
    ocp_namespace: Optional[str] = None,
    error_message: Optional[str] = None,
    stack_trace: Optional[str] = None,
) -> dict:
    """
    Execute the LangChain ReAct triage agent for a failed test case.

    Fast path: tries the FastClassifier first (single LLM call, ~50ms).
    If the classifier is confident enough (>= CLASSIFIER_CONFIDENCE_THRESHOLD),
    returns immediately without running the full ReAct agent.

    Slow path: falls through to the full ReAct agent with 5 investigation tools.

    Stores full audit trail to MongoDB in both cases.
    Returns structured analysis dict.
    """
    # ── Fast path: single-call classifier ────────────────────────────────────
    if error_message or stack_trace:
        try:
            from app.services.training.classifier import FastClassifier
            quick = await FastClassifier.classify(
                test_name=test_name,
                error_message=error_message or "",
                stack_trace=stack_trace or "",
            )
            if quick is not None:
                await _store_audit_trail(test_case_id, f"fast_classifier:{test_name}", quick, [])
                return quick
        except Exception as fc_exc:
            logger.debug("FastClassifier skipped: %s", fc_exc)

    # ── Slow path: full ReAct agent ───────────────────────────────────────────
    llm = get_llm()
    tools = _get_tools()

    prompt = PromptTemplate.from_template(SYSTEM_PROMPT)
    agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=settings.is_development,
        max_iterations=10,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
        max_execution_time=settings.AI_TIMEOUT_SECONDS,
    )

    user_question = (
        f"Investigate why test '{test_name}' (ID: {test_case_id}) failed. "
        + (f"Backend service: '{service_name}'. " if service_name else "")
        + (f"Failure timestamp: {timestamp}. " if timestamp else "")
        + (f"Ran on OpenShift pod '{ocp_pod_name}' in namespace '{ocp_namespace}'." if ocp_pod_name else "")
    )

    logger.info(f"Starting AI triage for test: {test_name} (provider: {settings.LLM_PROVIDER})")

    try:
        result = await executor.ainvoke({"input": user_question})
        raw_output = result.get("output", "{}")
        intermediate_steps = result.get("intermediate_steps", [])

        # Parse JSON from agent output
        analysis = _parse_agent_output(raw_output)
        analysis["llm_provider"] = settings.LLM_PROVIDER
        analysis["llm_model"] = settings.LLM_MODEL
        analysis["requires_human_review"] = analysis.get("confidence_score", 0) < settings.AI_CONFIDENCE_THRESHOLD

    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        analysis = _fallback_analysis(str(e))
        intermediate_steps = []

    # Store full audit trail to MongoDB
    await _store_audit_trail(test_case_id, user_question, analysis, intermediate_steps)

    return analysis


def _parse_agent_output(raw: str) -> dict:
    """Extract and parse JSON from agent final answer."""
    # Try to extract JSON block from output
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    # Try to find JSON within the output
    import re
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return _fallback_analysis("Could not parse structured output from agent")


def _fallback_analysis(error_msg: str) -> dict:
    return {
        "root_cause_summary": f"AI analysis could not complete. Reason: {error_msg}. Manual investigation required.",
        "failure_category": "UNKNOWN",
        "backend_error_found": False,
        "pod_issue_found": False,
        "is_flaky": False,
        "confidence_score": 0,
        "recommended_actions": ["Review stack trace manually", "Check application logs", "Re-run test to check for flakiness"],
        "evidence_references": [],
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "requires_human_review": True,
    }


async def _store_audit_trail(test_case_id: str, prompt: str, analysis: dict, steps: list) -> None:
    """Persist full agent reasoning trace to MongoDB for auditing."""
    db = get_mongo_db()
    await db[Collections.AI_ANALYSIS_PAYLOADS].update_one(
        {"test_case_id": test_case_id},
        {"$set": {
            "test_case_id": test_case_id,
            "prompt": prompt,
            "analysis": analysis,
            "intermediate_steps": [str(s) for s in steps],
            "llm_provider": settings.LLM_PROVIDER,
            "llm_model": settings.LLM_MODEL,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
