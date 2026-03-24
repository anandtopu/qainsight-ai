import api from './api'

export type PipelineStatus = 'pending' | 'running' | 'completed' | 'failed' | 'partial'
export type StageStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'

export interface AgentStageResult {
  stage_name: string
  status: StageStatus
  started_at: string | null
  completed_at: string | null
  result_data: Record<string, unknown> | null
  error: string | null
}

export interface AgentPipelineRun {
  id: string
  test_run_id: string
  workflow_type: 'offline' | 'live'
  status: PipelineStatus
  started_at: string | null
  completed_at: string | null
  error: string | null
  created_at: string
}

export interface RunSummary {
  test_run_id: string
  project_id: string
  build_number: string
  executive_summary: string
  markdown_report: string
  anomaly_count: number
  is_regression: boolean
  analysis_count: number
  generated_at: string
}

export interface ActiveLiveRun {
  run_id: string
  project_id: string
  build_number: string
  total: number
  passed: number
  failed: number
  skipped: number
  broken: number
  pass_rate: number
  current_test: string | null
  started_at: string
}

const agentService = {
  listPipelines: (runId?: string, status?: string, limit = 20) =>
    api.get<AgentPipelineRun[]>('/api/v1/agents/pipelines', {
      params: { run_id: runId, status, limit },
    }),

  getPipeline: (pipelineId: string) =>
    api.get<AgentPipelineRun>(`/api/v1/agents/pipelines/${pipelineId}`),

  getStages: (pipelineId: string) =>
    api.get<AgentStageResult[]>(`/api/v1/agents/pipelines/${pipelineId}/stages`),

  triggerPipeline: (testRunId: string) =>
    api.post<{ message: string; task_id: string; run_id: string }>(
      '/api/v1/agents/pipelines/trigger',
      { test_run_id: testRunId },
    ),

  getActiveLiveRuns: () =>
    api.get<{ active_runs: ActiveLiveRun[] }>('/api/v1/agents/active-runs'),

  getRunSummary: (runId: string) =>
    api.get<RunSummary>(`/api/v1/agents/runs/${runId}/summary`),
}

export default agentService
