import useSWR from 'swr'
import agentService from '@/services/agentService'
import type { ActiveLiveRun, AgentPipelineRun, AgentStageResult, RunSummary } from '@/types/agent'
import { useActiveProjectId } from './useProjectScopedSWR'

export function usePipelines(runId?: string) {
  const projectId = useActiveProjectId()
  const key = runId
    ? `/pipelines?run=${runId}`
    : projectId
      ? `/pipelines?project=${projectId}`
      : '/pipelines'
  return useSWR<AgentPipelineRun[]>(
    key,
    () => agentService.listPipelines(runId, projectId ?? undefined),
    { refreshInterval: 5000, revalidateOnFocus: false },
  )
}

export function usePipelineStages(pipelineId: string | null) {
  return useSWR<AgentStageResult[]>(
    pipelineId ? `/pipelines/${pipelineId}/stages` : null,
    () => agentService.getStages(pipelineId ?? ''),
    { refreshInterval: 3000, revalidateOnFocus: false },
  )
}

export function useRunSummary(runId: string | null) {
  return useSWR<RunSummary>(
    runId ? `/run-summary/${runId}` : null,
    () => agentService.getRunSummary(runId ?? ''),
    { revalidateOnFocus: false },
  )
}

export function useActiveLiveRuns() {
  return useSWR<ActiveLiveRun[]>(
    '/active-live-runs',
    () => agentService.getActiveLiveRuns().then((response) => response.active_runs),
    { refreshInterval: 2000, revalidateOnFocus: false },
  )
}
