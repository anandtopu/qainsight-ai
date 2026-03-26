import { api } from './api'

// ─── Types ───────────────────────────────────────────────────────────────────

export interface TestStep {
  step_number: number
  action: string
  expected_result: string
}

export interface AIReviewIssue {
  severity: string
  category: string
  description: string
  step?: number
}

export interface AIReviewSuggestion {
  field: string
  suggestion: string
}

export interface AIReviewResult {
  quality_score?: number
  grade?: string
  summary?: string
  score_breakdown?: Record<string, number>
  issues?: AIReviewIssue[]
  suggestions?: AIReviewSuggestion[]
  best_practices_violations?: string[]
  coverage_gaps?: string[]
  positive_aspects?: string[]
  error?: string
}

export interface ManagedTestCase {
  id: string
  project_id: string
  title: string
  description?: string
  objective?: string
  preconditions?: string
  steps?: TestStep[]
  expected_result?: string
  test_data?: string
  test_type: string
  priority: string
  severity: string
  feature_area?: string
  tags?: string[]
  status: string
  version: number
  author_id?: string
  assignee_id?: string
  reviewer_id?: string
  is_automated: boolean
  automation_status: string
  test_fingerprint?: string
  ai_generated: boolean
  ai_quality_score?: number
  ai_review_notes?: AIReviewResult
  estimated_duration_minutes?: number
  last_executed_at?: string
  last_execution_status?: string
  created_at: string
  updated_at: string
}

export interface TestCaseVersion {
  id: string
  test_case_id: string
  version: number
  title: string
  description?: string
  steps?: TestStep[]
  expected_result?: string
  status: string
  changed_by_id?: string
  change_summary?: string
  change_type: string
  created_at: string
}

export interface TestCaseReview {
  id: string
  test_case_id: string
  reviewer_id?: string
  requested_by_id?: string
  status: string
  ai_review_completed: boolean
  ai_quality_score?: number
  ai_review_notes?: AIReviewResult
  ai_reviewed_at?: string
  human_notes?: string
  reviewed_at?: string
  created_at: string
  updated_at: string
}

export interface TestCaseComment {
  id: string
  test_case_id: string
  author_id?: string
  content: string
  comment_type: string
  parent_id?: string
  step_number?: number
  is_resolved: boolean
  created_at: string
  updated_at: string
}

export interface TestPlan {
  id: string
  project_id: string
  name: string
  description?: string
  objective?: string
  status: string
  planned_start_date?: string
  planned_end_date?: string
  actual_start_date?: string
  actual_end_date?: string
  created_by_id?: string
  assigned_to_id?: string
  ai_generated: boolean
  total_cases: number
  executed_cases: number
  passed_cases: number
  failed_cases: number
  blocked_cases: number
  created_at: string
  updated_at: string
}

export interface TestPlanItem {
  id: string
  plan_id: string
  test_case_id: string
  order_index: number
  priority_override?: string
  execution_status: string
  executed_by_id?: string
  executed_at?: string
  execution_notes?: string
  actual_duration_minutes?: number
  created_at: string
}

export interface RiskItem {
  risk: string
  likelihood: string
  impact: string
  mitigation: string
}

export interface TestTypeItem {
  type: string
  priority: string
  tools: string[]
  coverage_target_pct: number
  rationale: string
}

export interface EnvironmentItem {
  name: string
  type: string
  purpose: string
}

export interface TestStrategy {
  id: string
  project_id: string
  name: string
  version_label: string
  status: string
  objective?: string
  scope?: string
  out_of_scope?: string
  test_approach?: string
  risk_assessment?: RiskItem[]
  test_types?: TestTypeItem[]
  entry_criteria?: string[]
  exit_criteria?: string[]
  environments?: EnvironmentItem[]
  automation_approach?: string
  defect_management?: string
  ai_generated: boolean
  ai_model_used?: string
  created_by_id?: string
  approved_by_id?: string
  approved_at?: string
  created_at: string
  updated_at: string
}

export interface AuditLogEntry {
  id: string
  entity_type: string
  entity_id: string
  project_id?: string
  action: string
  actor_id?: string
  actor_name?: string
  old_values?: Record<string, unknown>
  new_values?: Record<string, unknown>
  details?: string
  created_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export interface AIGenerateResponse {
  test_cases: Partial<ManagedTestCase>[]
  coverage_summary?: string
  gaps_noted: string[]
  created_ids: string[]
}

export interface AICoverageResponse {
  coverage_score?: number
  covered_areas?: string[]
  uncovered_areas?: string[]
  recommended_new_tests?: Array<{ title: string; priority: string; rationale: string }>
  summary?: string
}

// ─── Service ─────────────────────────────────────────────────────────────────

export const testManagementService = {
  // Test Cases
  listCases: (projectId: string, params?: Record<string, unknown>): Promise<PaginatedResponse<ManagedTestCase>> =>
    api.get('/api/v1/test-management/cases', { params: { project_id: projectId, ...params } }).then(r => r.data),

  createCase: (data: Partial<ManagedTestCase>): Promise<ManagedTestCase> =>
    api.post('/api/v1/test-management/cases', data).then(r => r.data),

  getCase: (id: string): Promise<ManagedTestCase> =>
    api.get(`/api/v1/test-management/cases/${id}`).then(r => r.data),

  updateCase: (id: string, data: Partial<ManagedTestCase> & { change_summary?: string }): Promise<ManagedTestCase> =>
    api.patch(`/api/v1/test-management/cases/${id}`, data).then(r => r.data),

  deleteCase: (id: string): Promise<void> =>
    api.delete(`/api/v1/test-management/cases/${id}`).then(r => r.data),

  getCaseHistory: (id: string): Promise<TestCaseVersion[]> =>
    api.get(`/api/v1/test-management/cases/${id}/history`).then(r => r.data),

  getCaseReviews: (id: string): Promise<TestCaseReview[]> =>
    api.get(`/api/v1/test-management/cases/${id}/reviews`).then(r => r.data),

  getCaseComments: (id: string): Promise<TestCaseComment[]> =>
    api.get(`/api/v1/test-management/cases/${id}/comments`).then(r => r.data),

  addComment: (id: string, data: { content: string; comment_type: string; step_number?: number }): Promise<TestCaseComment> =>
    api.post(`/api/v1/test-management/cases/${id}/comments`, data).then(r => r.data),

  requestReview: (id: string): Promise<TestCaseReview> =>
    api.post(`/api/v1/test-management/cases/${id}/request-review`).then(r => r.data),

  reviewAction: (id: string, action: string, notes?: string): Promise<ManagedTestCase> =>
    api.post(`/api/v1/test-management/cases/${id}/review-action`, { action, notes }).then(r => r.data),

  // AI operations
  aiGenerate: (data: { project_id: string; requirements: string; persist: boolean }): Promise<AIGenerateResponse> =>
    api.post('/api/v1/test-management/cases/ai-generate', data).then(r => r.data),

  aiReview: (id: string): Promise<AIReviewResult> =>
    api.post(`/api/v1/test-management/cases/${id}/ai-review`).then(r => r.data),

  aiCoverage: (data: { project_id: string; requirements: string }): Promise<AICoverageResponse> =>
    api.post('/api/v1/test-management/cases/ai-coverage', data).then(r => r.data),

  // Test Plans
  listPlans: (projectId: string, params?: Record<string, unknown>): Promise<PaginatedResponse<TestPlan>> =>
    api.get('/api/v1/test-management/plans', { params: { project_id: projectId, ...params } }).then(r => r.data),

  createPlan: (data: Partial<TestPlan>): Promise<TestPlan> =>
    api.post('/api/v1/test-management/plans', data).then(r => r.data),

  getPlan: (id: string): Promise<TestPlan> =>
    api.get(`/api/v1/test-management/plans/${id}`).then(r => r.data),

  updatePlan: (id: string, data: Partial<TestPlan>): Promise<TestPlan> =>
    api.patch(`/api/v1/test-management/plans/${id}`, data).then(r => r.data),

  getPlanItems: (id: string): Promise<TestPlanItem[]> =>
    api.get(`/api/v1/test-management/plans/${id}/items`).then(r => r.data),

  addPlanItem: (planId: string, data: { test_case_id: string; order_index?: number }): Promise<TestPlanItem> =>
    api.post(`/api/v1/test-management/plans/${planId}/items`, data).then(r => r.data),

  removePlanItem: (planId: string, itemId: string): Promise<void> =>
    api.delete(`/api/v1/test-management/plans/${planId}/items/${itemId}`).then(r => r.data),

  executeItem: (planId: string, itemId: string, data: { execution_status: string; execution_notes?: string; actual_duration_minutes?: number }): Promise<TestPlanItem> =>
    api.post(`/api/v1/test-management/plans/${planId}/items/${itemId}/execute`, data).then(r => r.data),

  aiCreatePlan: (data: { project_id: string; plan_name?: string; constraints?: string }): Promise<TestPlan> =>
    api.post('/api/v1/test-management/plans/ai-create', data).then(r => r.data),

  // Strategies
  listStrategies: (projectId: string): Promise<TestStrategy[]> =>
    api.get('/api/v1/test-management/strategies', { params: { project_id: projectId } }).then(r => r.data),

  getStrategy: (id: string): Promise<TestStrategy> =>
    api.get(`/api/v1/test-management/strategies/${id}`).then(r => r.data),

  updateStrategy: (id: string, data: Partial<TestStrategy>): Promise<TestStrategy> =>
    api.patch(`/api/v1/test-management/strategies/${id}`, data).then(r => r.data),

  aiGenerateStrategy: (data: { project_id: string; project_context: string; strategy_name?: string }): Promise<TestStrategy> =>
    api.post('/api/v1/test-management/strategies/ai-generate', data).then(r => r.data),

  // Audit Log
  getAuditLog: (projectId: string, params?: { entity_type?: string; action?: string; page?: number; size?: number }): Promise<PaginatedResponse<AuditLogEntry>> =>
    api.get('/api/v1/test-management/audit-log', { params: { project_id: projectId, ...params } }).then(r => r.data),
}
