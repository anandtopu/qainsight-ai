import { api } from './api'

export interface AnalyzeRequest {
  test_case_id: string
  service_name?: string
  timestamp?: string
  ocp_pod_name?: string
  ocp_namespace?: string
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
  evidence_references: Array<{ source: string; reference_id: string; excerpt: string }>
  llm_provider: string
  llm_model: string
  requires_human_review: boolean
}

export const aiService = {
  analyze: (request: AnalyzeRequest): Promise<AnalysisResult> =>
    api.post('/api/v1/analyze', request).then(r => r.data),

  createJiraTicket: (payload: {
    project_key: string
    test_case_id: string
    test_name: string
    run_id: string
    ai_summary: string
    recommended_action: string
  }) => api.post('/api/v1/integrations/jira', payload).then(r => r.data),
}
