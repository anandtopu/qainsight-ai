import useSWR from 'swr'
import agentService, { AgentPipelineRun, AgentStageResult, ActiveLiveRun, RunSummary } from '@/services/agentService'
import { useProjectStore } from '@/store/projectStore'

export function usePipelines(runId?: string) {
  const projectId = useProjectStore(s => s.activeProjectId)
  const key = runId
    ? `/pipelines?run=${runId}`
    : projectId
      ? `/pipelines?project=${projectId}`
      : '/pipelines'
  return useSWR<AgentPipelineRun[]>(
    key,
    () => agentService.listPipelines(runId, projectId ?? undefined).then((r) => r.data),
    { refreshInterval: 5000, revalidateOnFocus: false },
  )
}

export function usePipelineStages(pipelineId: string | null) {
  return useSWR<AgentStageResult[]>(
    pipelineId ? `/pipelines/${pipelineId}/stages` : null,
    () => agentService.getStages(pipelineId ?? '').then((r) => r.data),
    { refreshInterval: 3000, revalidateOnFocus: false },
  )
}

export function useRunSummary(runId: string | null) {
  return useSWR<RunSummary>(
    runId ? `/run-summary/${runId}` : null,
    () => agentService.getRunSummary(runId ?? '').then((r) => r.data),
    { revalidateOnFocus: false },
  )
}

export function useActiveLiveRuns() {
  return useSWR<ActiveLiveRun[]>(
    '/active-live-runs',
    () => agentService.getActiveLiveRuns().then((r) => r.data.active_runs),
    { refreshInterval: 2000, revalidateOnFocus: false },
  )
}
