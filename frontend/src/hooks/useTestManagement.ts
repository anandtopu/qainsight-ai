import useSWR from 'swr'
import { testManagementService } from '@/services/testManagementService'
import { useActiveProjectId, useProjectScopedSWR } from './useProjectScopedSWR'

export function useTestCases(params?: Record<string, unknown>) {
  return useProjectScopedSWR(
    'tm-cases',
    (projectId) => testManagementService.listCases(projectId, params),
    { refreshInterval: 60_000 },
    [params],
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
  return useProjectScopedSWR(
    'tm-plans',
    (projectId) => testManagementService.listPlans(projectId, params),
    { refreshInterval: 60_000 },
    [params],
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
  return useProjectScopedSWR(
    'tm-strategies',
    (projectId) => testManagementService.listStrategies(projectId),
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
  const projectId = useActiveProjectId()
  return useSWR(
    projectId ? ['tm-audit', projectId, params] : null,
    () => testManagementService.getAuditLog(projectId as string, params),
    { refreshInterval: 60_000 }
  )
}
