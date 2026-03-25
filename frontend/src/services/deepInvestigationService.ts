import { api } from './api'

export interface FailureCluster {
  cluster_id: string
  label: string
  representative_error: string | null
  member_test_ids: string[]
  size: number
  cohesion_score: number | null
}

export interface DeepFinding {
  cluster_id: string
  root_cause: string | null
  failure_category: string | null
  confidence_score: number | null
  causal_chain: CausalStep[] | null
  evidence: EvidenceItem[] | null
  affected_services: string[] | null
  contract_violations: ContractViolation[] | null
  recommended_actions: string[] | null
}

export interface CausalStep {
  step: number
  service: string
  finding: string
}

export interface EvidenceItem {
  source: string
  excerpt: string
}

export interface ContractViolation {
  field_path: string
  violation_type: string
  expected: string
  actual: string
  severity: 'critical' | 'warning' | 'info'
  endpoint?: string
  test_case_id?: string
}

export interface ReleaseDecision {
  run_id: string
  recommendation: 'GO' | 'NO_GO' | 'CONDITIONAL_GO'
  risk_score: number
  blocking_issues: string[]
  conditions_for_go: string[]
  reasoning: string | null
  human_override: string | null
  pass_rate: number | null
  build_number: string | null
}

export const deepInvestigationService = {
  triggerDeep: (runId: string, mode: 'deep' | 'offline' = 'deep') =>
    api.post(`/api/v1/deep-investigate/${runId}`, { mode }).then(r => r.data),

  getClusters: (runId: string) =>
    api.get<FailureCluster[]>(`/api/v1/deep-investigate/${runId}/clusters`).then(r => r.data),

  getFindings: (runId: string) =>
    api.get<DeepFinding[]>(`/api/v1/deep-investigate/${runId}/findings`).then(r => r.data),

  getReleaseDecision: (runId: string) =>
    api.get<ReleaseDecision>(`/api/v1/release-readiness/${runId}`).then(r => r.data),

  overrideRelease: (runId: string, override_recommendation: string, reason: string) =>
    api.post<ReleaseDecision>(`/api/v1/release-readiness/${runId}/override`, {
      override_recommendation,
      reason,
    }).then(r => r.data),
}
