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
