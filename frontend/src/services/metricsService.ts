import { api } from './api'

export interface TrendPoint {
  date: string
  passed: number
  failed: number
  skipped: number
  broken: number
  pass_rate: number
}

export const metricsService = {
  getSummary: (projectId: string, days = 7) =>
    api.get('/api/v1/metrics/summary', { params: { project_id: projectId, days } }).then(r => r.data),

  getTrends: (projectId: string, days = 7) =>
    api.get('/api/v1/metrics/trends', { params: { project_id: projectId, days } }).then(r => r.data),
}
