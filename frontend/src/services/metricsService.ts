import { api } from './api'

export const metricsService = {
  getSummary: (projectId: string, days = 7) =>
    api.get('/api/v1/metrics/summary', { params: { project_id: projectId, days } }).then(r => r.data),

  getTrends: (projectId: string, days = 7) =>
    api.get('/api/v1/metrics/trends', { params: { project_id: projectId, days } }).then(r => r.data),
}
