import useSWR from 'swr'
import { runsService } from '@/services/runsService'
import { useProjectStore } from '@/store/projectStore'

export function useRuns(params?: Record<string, unknown>) {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['runs', projectId, params] : null,
    () => runsService.list(projectId!, params),
    { refreshInterval: 15_000 }
  )
}

export function useRun(runId?: string) {
  return useSWR(runId ? ['run', runId] : null, () => runsService.get(runId!))
}

export function useTestCases(runId?: string, params?: Record<string, unknown>) {
  return useSWR(
    runId ? ['test-cases', runId, params] : null,
    () => runsService.listTests(runId!, params)
  )
}

export function useTestCase(runId?: string, testId?: string) {
  return useSWR(
    runId && testId ? ['test-case', runId, testId] : null,
    () => runsService.getTest(runId!, testId!)
  )
}
