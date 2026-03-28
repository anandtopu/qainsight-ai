import type {
  CoverageResponse,
  DefectResponse,
  FailureCategoryItem,
  FlakyTestItem,
  SuiteDetailResponse,
  TopFailingItem,
} from '@/types/analytics'
import { getData } from './http'

export const analyticsService = {
  getFlakyTests: (projectId: string, days = 30) =>
    getData<{ items: FlakyTestItem[] }>('/api/v1/analytics/flaky-tests', { params: { project_id: projectId, days } }),

  getFailureCategories: (projectId: string, days = 30) =>
    getData<{ items: FailureCategoryItem[] }>('/api/v1/analytics/failure-categories', { params: { project_id: projectId, days } }),

  getTopFailing: (projectId: string, days = 30) =>
    getData<{ items: TopFailingItem[] }>('/api/v1/analytics/top-failing', { params: { project_id: projectId, days } }),

  getCoverage: (projectId: string, days = 30) =>
    getData<CoverageResponse>('/api/v1/analytics/coverage', { params: { project_id: projectId, days } }),

  getDefects: (projectId: string, params?: Record<string, unknown>) =>
    getData<DefectResponse>('/api/v1/analytics/defects', { params: { project_id: projectId, ...params } }),

  getAiSummary: (projectId: string, days = 30) =>
    getData('/api/v1/analytics/ai-summary', { params: { project_id: projectId, days } }),

  getSuiteDetail: (projectId: string, suiteName: string, days = 30) =>
    getData<SuiteDetailResponse>('/api/v1/analytics/suite-detail', {
      params: { project_id: projectId, suite_name: suiteName, days },
    }),
}
