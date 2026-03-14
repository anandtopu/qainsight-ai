import useSWR from 'swr'
import { metricsService } from '@/services/metricsService'
import { useProjectStore } from '@/store/projectStore'

export function useDashboardSummary(days = 7) {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['metrics-summary', projectId, days] : null,
    () => metricsService.getSummary(projectId!, days),
    { refreshInterval: 30_000 }
  )
}

export function useTrendData(days = 7) {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['metrics-trends', projectId, days] : null,
    () => metricsService.getTrends(projectId!, days),
    { refreshInterval: 60_000 }
  )
}
