import type {
  AICoverageResponse,
  AIGenerateResponse,
  AIReviewResult,
  AuditLogEntry,
  ManagedTestCase,
  PaginatedResponse,
  TestCaseComment,
  TestCaseReview,
  TestCaseVersion,
  TestPlan,
  TestPlanItem,
  TestStrategy,
} from '@/types/test-management'
import { deleteData, getData, patchData, postData } from './http'

export const testManagementService = {
  // Test Cases
  listCases: (projectId: string, params?: Record<string, unknown>): Promise<PaginatedResponse<ManagedTestCase>> =>
    getData('/api/v1/test-management/cases', { params: { project_id: projectId, ...params } }),

  createCase: (data: Partial<ManagedTestCase>): Promise<ManagedTestCase> =>
    postData('/api/v1/test-management/cases', data),

  getCase: (id: string): Promise<ManagedTestCase> =>
    getData(`/api/v1/test-management/cases/${id}`),

  updateCase: (id: string, data: Partial<ManagedTestCase> & { change_summary?: string }): Promise<ManagedTestCase> =>
    patchData(`/api/v1/test-management/cases/${id}`, data),

  deleteCase: (id: string): Promise<void> =>
    deleteData(`/api/v1/test-management/cases/${id}`),

  getCaseHistory: (id: string): Promise<TestCaseVersion[]> =>
    getData(`/api/v1/test-management/cases/${id}/history`),

  getCaseReviews: (id: string): Promise<TestCaseReview[]> =>
    getData(`/api/v1/test-management/cases/${id}/reviews`),

  getCaseComments: (id: string): Promise<TestCaseComment[]> =>
    getData(`/api/v1/test-management/cases/${id}/comments`),

  addComment: (id: string, data: { content: string; comment_type: string; step_number?: number }): Promise<TestCaseComment> =>
    postData(`/api/v1/test-management/cases/${id}/comments`, data),

  requestReview: (id: string): Promise<TestCaseReview> =>
    postData(`/api/v1/test-management/cases/${id}/request-review`),

  reviewAction: (id: string, action: string, notes?: string): Promise<ManagedTestCase> =>
    postData(`/api/v1/test-management/cases/${id}/review-action`, { action, notes }),

  // AI operations
  aiGenerate: (data: { project_id: string; requirements: string; persist: boolean }): Promise<AIGenerateResponse> =>
    postData('/api/v1/test-management/cases/ai-generate', data),

  aiGenerateAsync: (data: { project_id: string; requirements: string; persist: boolean }): Promise<{ task_id: string; status: string }> =>
    postData('/api/v1/test-management/cases/ai-generate/async', data),

  aiTaskStatus: (taskId: string): Promise<{ task_id: string; status: string; result?: AIGenerateResponse; error?: string }> =>
    getData(`/api/v1/test-management/cases/ai-task/${taskId}`),

  aiReview: (id: string): Promise<AIReviewResult> =>
    postData(`/api/v1/test-management/cases/${id}/ai-review`),

  aiCoverage: (data: { project_id: string; requirements: string }): Promise<AICoverageResponse> =>
    postData('/api/v1/test-management/cases/ai-coverage', data),

  // Test Plans
  listPlans: (projectId: string, params?: Record<string, unknown>): Promise<PaginatedResponse<TestPlan>> =>
    getData('/api/v1/test-management/plans', { params: { project_id: projectId, ...params } }),

  createPlan: (data: Partial<TestPlan>): Promise<TestPlan> =>
    postData('/api/v1/test-management/plans', data),

  getPlan: (id: string): Promise<TestPlan> =>
    getData(`/api/v1/test-management/plans/${id}`),

  updatePlan: (id: string, data: Partial<TestPlan>): Promise<TestPlan> =>
    patchData(`/api/v1/test-management/plans/${id}`, data),

  getPlanItems: (id: string): Promise<TestPlanItem[]> =>
    getData(`/api/v1/test-management/plans/${id}/items`),

  addPlanItem: (planId: string, data: { test_case_id: string; order_index?: number }): Promise<TestPlanItem> =>
    postData(`/api/v1/test-management/plans/${planId}/items`, data),

  removePlanItem: (planId: string, itemId: string): Promise<void> =>
    deleteData(`/api/v1/test-management/plans/${planId}/items/${itemId}`),

  executeItem: (planId: string, itemId: string, data: { execution_status: string; execution_notes?: string; actual_duration_minutes?: number }): Promise<TestPlanItem> =>
    postData(`/api/v1/test-management/plans/${planId}/items/${itemId}/execute`, data),

  aiCreatePlan: (data: { project_id: string; plan_name?: string; constraints?: string }): Promise<TestPlan> =>
    postData('/api/v1/test-management/plans/ai-create', data),

  aiCreatePlanAsync: (data: { project_id: string; plan_name?: string; constraints?: string }): Promise<{ task_id: string; status: string }> =>
    postData('/api/v1/test-management/plans/ai-create/async', data),

  // Strategies
  listStrategies: (projectId: string): Promise<TestStrategy[]> =>
    getData('/api/v1/test-management/strategies', { params: { project_id: projectId } }),

  getStrategy: (id: string): Promise<TestStrategy> =>
    getData(`/api/v1/test-management/strategies/${id}`),

  updateStrategy: (id: string, data: Partial<TestStrategy>): Promise<TestStrategy> =>
    patchData(`/api/v1/test-management/strategies/${id}`, data),

  aiGenerateStrategy: (data: { project_id: string; project_context: string; strategy_name?: string }): Promise<TestStrategy> =>
    postData('/api/v1/test-management/strategies/ai-generate', data),

  aiGenerateStrategyAsync: (data: { project_id: string; project_context: string; strategy_name?: string }): Promise<{ task_id: string; status: string }> =>
    postData('/api/v1/test-management/strategies/ai-generate/async', data),

  // Audit Log
  getAuditLog: (projectId: string, params?: { entity_type?: string; action?: string; page?: number; size?: number }): Promise<PaginatedResponse<AuditLogEntry>> =>
    getData('/api/v1/test-management/audit', { params: { project_id: projectId, ...params } }),
}
export type {
  AICoverageResponse,
  AIGenerateResponse,
  AIReviewResult,
  AuditLogEntry,
  ManagedTestCase,
  PaginatedResponse,
  TestCaseComment,
  TestCaseReview,
  TestCaseVersion,
  TestPlan,
  TestPlanItem,
  TestStep,
  TestStrategy,
} from '@/types/test-management'
