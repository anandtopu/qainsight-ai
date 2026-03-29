import { useAuthStore } from '@/store/authStore'

type Role = 'VIEWER' | 'TESTER' | 'QA_ENGINEER' | 'QA_LEAD' | 'ADMIN'

const ROLE_ORDER: Role[] = ['VIEWER', 'TESTER', 'QA_ENGINEER', 'QA_LEAD', 'ADMIN']

export function usePermissions() {
  const user = useAuthStore((s) => s.user)
  const role = (user?.role ?? 'VIEWER') as Role

  function hasRole(minRole: Role): boolean {
    return ROLE_ORDER.indexOf(role) >= ROLE_ORDER.indexOf(minRole)
  }

  return {
    role,
    isAdmin: role === 'ADMIN',
    isQaLead: hasRole('QA_LEAD'),
    isQaEngineer: hasRole('QA_ENGINEER'),
    canManageUsers: role === 'ADMIN',
    canManageProjectMembers: hasRole('QA_LEAD'),
    canGenerateApiKeys: hasRole('QA_ENGINEER'),
    canTriggerLlm: hasRole('QA_ENGINEER'),
    hasRole,
  }
}