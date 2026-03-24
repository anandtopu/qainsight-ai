"""AI triage analysis endpoint."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_role
from app.db.postgres import get_db
from app.models.postgres import AIAnalysis, FailureCategory, TestCase, UserRole
from app.models.schemas import AnalysisResponse, AnalyzeRequest
from app.services.agent import run_triage_agent

router = APIRouter(prefix="/api/v1", tags=["AI Analysis"])


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    dependencies=[Depends(require_role(UserRole.QA_ENGINEER))],
)
async def analyze_test_case(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger the LangChain ReAct agent to investigate a failed test case.
    Returns a structured root-cause analysis with confidence scoring.
    """
    # Fetch test case details
    result = await db.execute(
        select(TestCase).where(TestCase.id == request.test_case_id)
    )
    tc = result.scalar_one_or_none()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")

    # Run the AI agent
    analysis = await run_triage_agent(
        test_case_id=str(tc.id),
        test_name=tc.test_name,
        service_name=request.service_name,
        timestamp=request.timestamp,
        ocp_pod_name=request.ocp_pod_name,
        ocp_namespace=request.ocp_namespace,
    )

    # Persist structured result to PostgreSQL
    category = analysis.get("failure_category", "UNKNOWN")
    try:
        fc = FailureCategory(category)
    except ValueError:
        fc = FailureCategory.UNKNOWN

    existing = await db.execute(
        select(AIAnalysis).where(AIAnalysis.test_case_id == tc.id)
    )
    ai_row = existing.scalar_one_or_none()

    if ai_row:
        ai_row.root_cause_summary = analysis.get("root_cause_summary")
        ai_row.failure_category = fc
        ai_row.backend_error_found = analysis.get("backend_error_found", False)
        ai_row.pod_issue_found = analysis.get("pod_issue_found", False)
        ai_row.is_flaky = analysis.get("is_flaky", False)
        ai_row.confidence_score = analysis.get("confidence_score", 0)
        ai_row.recommended_actions = analysis.get("recommended_actions", [])
        ai_row.evidence_references = analysis.get("evidence_references", [])
        ai_row.llm_provider = analysis.get("llm_provider")
        ai_row.llm_model = analysis.get("llm_model")
        ai_row.requires_human_review = analysis.get("requires_human_review", True)
    else:
        ai_row = AIAnalysis(
            test_case_id=tc.id,
            root_cause_summary=analysis.get("root_cause_summary"),
            failure_category=fc,
            backend_error_found=analysis.get("backend_error_found", False),
            pod_issue_found=analysis.get("pod_issue_found", False),
            is_flaky=analysis.get("is_flaky", False),
            confidence_score=analysis.get("confidence_score", 0),
            recommended_actions=analysis.get("recommended_actions", []),
            evidence_references=analysis.get("evidence_references", []),
            llm_provider=analysis.get("llm_provider"),
            llm_model=analysis.get("llm_model"),
            requires_human_review=analysis.get("requires_human_review", True),
        )
        db.add(ai_row)

    # Update test case failure category
    await db.execute(
        update(TestCase)
        .where(TestCase.id == tc.id)
        .values(failure_category=fc)
    )
    await db.commit()

    return AnalysisResponse(
        test_case_id=tc.id,
        **{k: v for k, v in analysis.items() if k not in ("llm_provider", "llm_model", "requires_human_review")},
        llm_provider=analysis.get("llm_provider", "unknown"),
        llm_model=analysis.get("llm_model", "unknown"),
        requires_human_review=analysis.get("requires_human_review", True),
    )
