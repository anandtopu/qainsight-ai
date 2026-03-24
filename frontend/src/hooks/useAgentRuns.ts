import useSWR from 'swr'
import agentService, { AgentPipelineRun, AgentStageResult } from '@/services/agentService'

const fetcher = (key: string) => {
  if (key.startsWith('/pipelines/') && key.endsWith('/stages')) {
    const pipelineId = key.replace('/pipelines/', '').replace('/stages', '')
    return agentService.getStages(pipelineId).then(r => r.data)
  }
  if (key.startsWith('/pipelines/')) {
    return agentService.getPipeline(key.replace('/pipelines/', '')).then(r => r.data)
  }
  return Promise.reject(new Error('Unknown key'))
}

export function usePipelines(runId?: string) {
  return useSWR(
    runId ? `/pipelines?run=${runId}` : '/pipelines',
    () => agentService.listPipelines(runId).then(r => r.data),
    { refreshInterval: 5000, revalidateOnFocus: false },
  )
}

export function usePipelineStages(pipelineId: string | null) {
  return useSWR(
    pipelineId ? `/pipelines/${pipelineId}/stages` : null,
    () => agentService.getStages(pipelineId!).then(r => r.data),
    { refreshInterval: 3000, revalidateOnFocus: false },
  )
}

export function useRunSummary(runId: string | null) {
  return useSWR(
    runId ? `/run-summary/${runId}` : null,
    () => agentService.getRunSummary(runId!).then(r => r.data),
    { revalidateOnFocus: false },
  )
}

export function useActiveLiveRuns() {
  return useSWR(
    '/active-live-runs',
    () => agentService.getActiveLiveRuns().then(r => r.data.active_runs),
    { refreshInterval: 2000, revalidateOnFocus: false },
  )
}
