import { api } from './api'

export const analyticsService = {
  getFlakyTests: (projectId: string, days = 30) =>
    api.get('/api/v1/analytics/flaky-tests', { params: { project_id: projectId, days } }).then(r => r.data),

  getFailureCategories: (projectId: string, days = 30) =>
    api.get('/api/v1/analytics/failure-categories', { params: { project_id: projectId, days } }).then(r => r.data),

  getTopFailing: (projectId: string, days = 30) =>
    api.get('/api/v1/analytics/top-failing', { params: { project_id: projectId, days } }).then(r => r.data),

  getCoverage: (projectId: string, days = 30) =>
    api.get('/api/v1/analytics/coverage', { params: { project_id: projectId, days } }).then(r => r.data),

  getDefects: (projectId: string, params?: Record<string, unknown>) =>
    api.get('/api/v1/analytics/defects', { params: { project_id: projectId, ...params } }).then(r => r.data),

  getAiSummary: (projectId: string, days = 30) =>
    api.get('/api/v1/analytics/ai-summary', { params: { project_id: projectId, days } }).then(r => r.data),
}
