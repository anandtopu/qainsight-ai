import { api } from './api'

export const runsService = {
  list: (projectId: string, params?: Record<string, unknown>) =>
    api.get('/api/v1/runs', { params: { project_id: projectId, ...params } }).then(r => r.data),

  get: (runId: string) =>
    api.get(`/api/v1/runs/${runId}`).then(r => r.data),

  listTests: (runId: string, params?: Record<string, unknown>) =>
    api.get(`/api/v1/runs/${runId}/tests`, { params }).then(r => r.data),

  getTest: (runId: string, testId: string) =>
    api.get(`/api/v1/runs/${runId}/tests/${testId}`).then(r => r.data),
}
