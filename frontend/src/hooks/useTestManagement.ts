import useSWR from 'swr'
import { testManagementService } from '@/services/testManagementService'
import { useProjectStore } from '@/store/projectStore'

export function useTestCases(params?: Record<string, unknown>) {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['tm-cases', projectId, params] : null,
    () => testManagementService.listCases(projectId as string, params),
    { refreshInterval: 60_000 }
  )
}

export function useTestCase(id?: string) {
  return useSWR(
    id ? ['tm-case', id] : null,
    () => testManagementService.getCase(id as string),
    { refreshInterval: 0 }
  )
}

export function useTestCaseHistory(id?: string) {
  return useSWR(
    id ? ['tm-case-history', id] : null,
    () => testManagementService.getCaseHistory(id as string),
    { refreshInterval: 0 }
  )
}

export function useTestCaseReviews(id?: string) {
  return useSWR(
    id ? ['tm-case-reviews', id] : null,
    () => testManagementService.getCaseReviews(id as string),
    { refreshInterval: 30_000 }
  )
}

export function useTestCaseComments(id?: string) {
  return useSWR(
    id ? ['tm-case-comments', id] : null,
    () => testManagementService.getCaseComments(id as string),
    { refreshInterval: 30_000 }
  )
}

export function useTestPlans(params?: Record<string, unknown>) {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['tm-plans', projectId, params] : null,
    () => testManagementService.listPlans(projectId as string, params),
    { refreshInterval: 60_000 }
  )
}

export function usePlan(id?: string) {
  return useSWR(
    id ? ['tm-plan', id] : null,
    () => testManagementService.getPlan(id as string),
    { refreshInterval: 0 }
  )
}

export function usePlanItems(planId?: string) {
  return useSWR(
    planId ? ['tm-plan-items', planId] : null,
    () => testManagementService.getPlanItems(planId as string),
    { refreshInterval: 30_000 }
  )
}

export function useStrategies() {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['tm-strategies', projectId] : null,
    () => testManagementService.listStrategies(projectId as string),
    { refreshInterval: 120_000 }
  )
}

export function useStrategy(id?: string) {
  return useSWR(
    id ? ['tm-strategy', id] : null,
    () => testManagementService.getStrategy(id as string),
    { refreshInterval: 0 }
  )
}

export function useAuditLog(params?: { entity_type?: string; action?: string; page?: number; size?: number }) {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['tm-audit', projectId, params] : null,
    () => testManagementService.getAuditLog(projectId as string, params),
    { refreshInterval: 60_000 }
  )
}
