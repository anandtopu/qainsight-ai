import { api } from './api'

export interface ReleasePhase {
  id: string
  release_id: string
  name: string
  phase_type: string
  status: string
  description: string | null
  order_index: number
  planned_start: string | null
  planned_end: string | null
  actual_start: string | null
  actual_end: string | null
  exit_criteria: Record<string, unknown> | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface Release {
  id: string
  project_id: string
  name: string
  version: string | null
  description: string | null
  status: string
  planned_date: string | null
  released_at: string | null
  created_at: string
  updated_at: string
  phases: ReleasePhase[]
  test_run_count?: number
}

export interface ReleaseDetail extends Release {
  linked_runs: LinkedRun[]
  metrics: ReleaseMetrics
}

export interface LinkedRun {
  id: string
  build_number: string | null
  status: string
  total_tests: number
  passed_tests: number
  failed_tests: number
  broken_tests: number
  skipped_tests: number
  pass_rate: number | null
  created_at: string
  phase_id: string | null
}

export interface ReleaseMetrics {
  total_runs: number
  total_tests: number
  total_passed: number
  total_failed: number
  avg_pass_rate: number | null
}

export const releasesService = {
  list: (projectId: string, status?: string) =>
    api.get('/api/v1/releases', { params: { project_id: projectId, ...(status ? { status } : {}) } })
       .then(r => r.data as { items: Release[]; total: number }),

  get: (id: string) =>
    api.get(`/api/v1/releases/${id}`).then(r => r.data as ReleaseDetail),

  create: (body: {
    project_id: string
    name: string
    version?: string
    description?: string
    status?: string
    planned_date?: string
    phases?: Partial<ReleasePhase>[]
  }) => api.post('/api/v1/releases', body).then(r => r.data as Release),

  update: (id: string, body: Partial<Release>) =>
    api.put(`/api/v1/releases/${id}`, body).then(r => r.data as Release),

  delete: (id: string) => api.delete(`/api/v1/releases/${id}`),

  addPhase: (releaseId: string, body: Partial<ReleasePhase>) =>
    api.post(`/api/v1/releases/${releaseId}/phases`, body).then(r => r.data as ReleasePhase),

  updatePhase: (releaseId: string, phaseId: string, body: Partial<ReleasePhase>) =>
    api.put(`/api/v1/releases/${releaseId}/phases/${phaseId}`, body).then(r => r.data as ReleasePhase),

  deletePhase: (releaseId: string, phaseId: string) =>
    api.delete(`/api/v1/releases/${releaseId}/phases/${phaseId}`),

  linkRun: (releaseId: string, testRunId: string, phaseId?: string) =>
    api.post(`/api/v1/releases/${releaseId}/test-runs`, { test_run_id: testRunId, phase_id: phaseId }),

  unlinkRun: (releaseId: string, runId: string) =>
    api.delete(`/api/v1/releases/${releaseId}/test-runs/${runId}`),
}
