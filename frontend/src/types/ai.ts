export interface AnalyzeRequest {
  test_case_id: string
  service_name?: string
  timestamp?: string
  ocp_pod_name?: string
  ocp_namespace?: string
}

export interface AnalysisEvidenceReference {
  source: string
  reference_id: string
  excerpt: string
}

export interface AnalysisResult {
  test_case_id: string
  root_cause_summary: string
  failure_category: string
  backend_error_found: boolean
  pod_issue_found: boolean
  is_flaky: boolean
  confidence_score: number
  recommended_actions: string[]
  evidence_references: AnalysisEvidenceReference[]
  llm_provider: string
  llm_model: string
  requires_human_review: boolean
}
