import useSWR from 'swr'
import { metricsService } from '@/services/metricsService'
import { analyticsService } from '@/services/analyticsService'
import { useProjectStore } from '@/store/projectStore'

export function useDashboardSummary(days = 7) {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['metrics-summary', projectId, days] : null,
    () => metricsService.getSummary(projectId as string, days),
    { refreshInterval: 30_000 }
  )
}

export function useTrendData(days = 7) {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['metrics-trends', projectId, days] : null,
    () => metricsService.getTrends(projectId as string, days),
    { refreshInterval: 60_000 }
  )
}

export function useFlakyTests(days = 30) {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['analytics-flaky', projectId, days] : null,
    () => analyticsService.getFlakyTests(projectId as string, days),
    { refreshInterval: 120_000 }
  )
}

export function useFailureCategories(days = 30) {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['analytics-categories', projectId, days] : null,
    () => analyticsService.getFailureCategories(projectId as string, days),
    { refreshInterval: 120_000 }
  )
}

export function useTopFailing(days = 30) {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['analytics-top-failing', projectId, days] : null,
    () => analyticsService.getTopFailing(projectId as string, days),
    { refreshInterval: 120_000 }
  )
}

export function useCoverage(days = 30) {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['analytics-coverage', projectId, days] : null,
    () => analyticsService.getCoverage(projectId as string, days),
    { refreshInterval: 120_000 }
  )
}

export function useDefects(page = 1, resolutionStatus?: string) {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['analytics-defects', projectId, page, resolutionStatus] : null,
    () => analyticsService.getDefects(projectId as string, { page, resolution_status: resolutionStatus }),
    { refreshInterval: 60_000 }
  )
}

export function useAiSummary(days = 30) {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['analytics-ai-summary', projectId, days] : null,
    () => analyticsService.getAiSummary(projectId as string, days),
    { refreshInterval: 120_000 }
  )
}
