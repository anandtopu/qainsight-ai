import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  AlertTriangle, Bot, ChevronDown, ChevronRight, GitBranch,
  Layers, Search, Shield, Zap,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { clsx } from 'clsx'
import PageHeader from '@/components/ui/PageHeader'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import EmptyState from '@/components/ui/EmptyState'
import { useFailureClusters, useDeepFindings } from '@/hooks/useDeepInvestigation'
import { deepInvestigationService } from '@/services/deepInvestigationService'
import type { DeepFinding, FailureCluster } from '@/types/deep-investigation'
import { useRuns } from '@/hooks/useRuns'

const CATEGORY_COLOUR: Record<string, string> = {
  PRODUCT_BUG:      'text-red-400',
  INFRASTRUCTURE:   'text-orange-400',
  AUTOMATION_DEFECT: 'text-yellow-400',
  TEST_DATA:        'text-blue-400',
  FLAKY:            'text-purple-400',
  UNKNOWN:          'text-slate-400',
}

const SEVERITY_COLOUR: Record<string, string> = {
  critical: 'text-red-400 bg-red-900/20 border-red-700/30',
  warning:  'text-yellow-400 bg-yellow-900/20 border-yellow-700/30',
  info:     'text-blue-400 bg-blue-900/20 border-blue-700/30',
}

function ClusterCard({
  cluster,
  finding,
  selected,
  onSelect,
}: {
  cluster: FailureCluster
  finding: DeepFinding | undefined
  selected: boolean
  onSelect: () => void
}) {
  const category = finding?.failure_category ?? 'UNKNOWN'
  return (
    <button
      onClick={onSelect}
      className={clsx(
        'w-full text-left card p-3 hover:border-slate-600 transition-colors',
        selected && 'border-blue-600 bg-blue-950/20',
      )}
    >
      <div className="flex items-center gap-2 mb-1">
        <Layers className="w-4 h-4 text-slate-400 shrink-0" />
        <span className="text-sm font-medium text-slate-200 truncate flex-1">{cluster.label}</span>
        <span className={clsx('text-xs font-mono shrink-0', CATEGORY_COLOUR[category])}>
          {category}
        </span>
      </div>
      <div className="flex items-center gap-3 pl-6">
        <span className="text-xs text-slate-500">{cluster.size} test{cluster.size !== 1 ? 's' : ''}</span>
        {finding?.confidence_score != null && (
          <span className="text-xs text-slate-500">conf {finding.confidence_score}%</span>
        )}
      </div>
    </button>
  )
}

function FindingPanel({ finding }: { finding: DeepFinding | undefined }) {
  const [showEvidence, setShowEvidence] = useState(false)
  const [showViolations, setShowViolations] = useState(false)

  if (!finding) {
    return (
      <div className="card flex flex-col items-center justify-center py-16 text-center">
        <Search className="w-10 h-10 text-slate-600 mb-3" />
        <p className="text-slate-400">Select a cluster to see deep investigation findings</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Root cause */}
      <div className="card">
        <div className="flex items-center gap-2 mb-2">
          <Bot className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-semibold text-slate-200">Root Cause</h3>
          {finding.failure_category && (
            <span className={clsx('ml-auto text-xs font-mono', CATEGORY_COLOUR[finding.failure_category])}>
              {finding.failure_category}
            </span>
          )}
          {finding.confidence_score != null && (
            <span className="text-xs text-slate-500">{finding.confidence_score}% confidence</span>
          )}
        </div>
        <p className="text-sm text-slate-300 leading-relaxed">
          {finding.root_cause ?? 'Root cause analysis pending.'}
        </p>
      </div>

      {/* Causal chain */}
      {finding.causal_chain && finding.causal_chain.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-emerald-400" />
            Causal Chain
          </h3>
          <div className="space-y-2">
            {finding.causal_chain.map((step, i) => (
              <div key={i} className="flex items-start gap-3">
                <span className="mt-0.5 w-5 h-5 rounded-full bg-slate-700 text-slate-300 text-xs flex items-center justify-center shrink-0">
                  {i + 1}
                </span>
                <div>
                  <span className="text-xs text-slate-400 font-mono">{step.service}</span>
                  <p className="text-xs text-slate-300 mt-0.5">{step.finding}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Affected services */}
      {finding.affected_services && finding.affected_services.length > 0 && (
        <div className="card py-3">
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Affected Services</p>
          <div className="flex flex-wrap gap-2">
            {finding.affected_services.map(svc => (
              <span key={svc} className="text-xs bg-slate-700 text-slate-300 px-2 py-0.5 rounded">
                {svc}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Recommended actions */}
      {finding.recommended_actions && finding.recommended_actions.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-slate-200 mb-2 flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-400" />
            Recommended Actions
          </h3>
          <ul className="space-y-1">
            {finding.recommended_actions.map((action, i) => (
              <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                <span className="text-amber-400 mt-0.5">→</span>
                {action}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Contract violations */}
      {finding.contract_violations && finding.contract_violations.length > 0 && (
        <div className="card">
          <button
            onClick={() => setShowViolations(v => !v)}
            className="w-full flex items-center gap-2 text-left"
          >
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <h3 className="text-sm font-semibold text-slate-200 flex-1">
              API Contract Violations ({finding.contract_violations.length})
            </h3>
            {showViolations
              ? <ChevronDown className="w-4 h-4 text-slate-500" />
              : <ChevronRight className="w-4 h-4 text-slate-500" />}
          </button>
          {showViolations && (
            <div className="mt-3 space-y-2">
              {finding.contract_violations.map((v, i) => (
                <div key={i} className={clsx('rounded border px-3 py-2 text-xs', SEVERITY_COLOUR[v.severity] ?? '')}>
                  <p className="font-mono font-medium">{v.field_path}</p>
                  <p className="text-slate-400 mt-0.5">{v.violation_type} — expected {v.expected}, got {v.actual}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Evidence */}
      {finding.evidence && finding.evidence.length > 0 && (
        <div className="card">
          <button
            onClick={() => setShowEvidence(v => !v)}
            className="w-full flex items-center gap-2 text-left"
          >
            <Shield className="w-4 h-4 text-slate-400" />
            <h3 className="text-sm font-semibold text-slate-200 flex-1">
              Evidence ({finding.evidence.length})
            </h3>
            {showEvidence
              ? <ChevronDown className="w-4 h-4 text-slate-500" />
              : <ChevronRight className="w-4 h-4 text-slate-500" />}
          </button>
          {showEvidence && (
            <div className="mt-3 space-y-2">
              {finding.evidence.map((e, i) => (
                <div key={i} className="bg-slate-900/60 rounded p-2">
                  <p className="text-xs text-slate-500 font-mono mb-1">{e.source}</p>
                  <p className="text-xs text-slate-300 font-mono whitespace-pre-wrap">{e.excerpt}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function DeepInvestigationPage() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const [selectedCluster, setSelectedCluster] = useState<string | null>(null)
  const [triggering, setTriggering] = useState(false)

  const { data: recentRuns } = useRuns({ page: 1, size: 1 })
  useEffect(() => {
    if (!runId && recentRuns?.items?.[0]?.id) {
      navigate(`/deep-investigate/${recentRuns.items[0].id}`, { replace: true })
    }
  }, [runId, recentRuns, navigate])

  const { data: clusters = [], isLoading: clustersLoading, mutate: mutateClusters } = useFailureClusters(runId ?? null)
  const { data: findings = [], isLoading: findingsLoading, mutate: mutateFindings } = useDeepFindings(runId ?? null)

  if (!runId) {
    return (
      <EmptyState
        icon={<Bot className="h-10 w-10" />}
        title="No run selected"
        description="Navigate to a test run and trigger deep investigation."
      />
    )
  }

  const findingByCluster = Object.fromEntries(
    findings.map(f => [f.cluster_id, f])
  )
  const selectedFinding = selectedCluster ? findingByCluster[selectedCluster] : undefined

  const handleTrigger = async () => {
    setTriggering(true)
    try {
      await deepInvestigationService.triggerDeep(runId, 'deep')
      toast.success('Deep investigation pipeline queued')
      setTimeout(() => { mutateClusters(); mutateFindings() }, 3000)
    } catch {
      toast.error('Failed to trigger deep investigation')
    } finally {
      setTriggering(false)
    }
  }

  const isLoading = clustersLoading || findingsLoading

  return (
    <div className="space-y-6">
      <PageHeader
        title="Deep Investigation"
        subtitle={`Semantic failure clustering and multi-source root cause analysis`}
        actions={
          <button
            onClick={handleTrigger}
            disabled={triggering}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            {triggering ? <LoadingSpinner size="sm" /> : <Bot className="w-4 h-4" />}
            {triggering ? 'Queueing…' : 'Run Deep Analysis'}
          </button>
        }
      />

      {isLoading ? (
        <div className="flex justify-center py-16"><LoadingSpinner size="lg" /></div>
      ) : clusters.length === 0 ? (
        <EmptyState
          icon={<Layers className="h-10 w-10" />}
          title="No clusters yet"
          description="Trigger a deep analysis to semantically cluster failures and investigate root causes."
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Cluster list */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
              Failure Clusters ({clusters.length})
            </h3>
            {clusters.map(cluster => (
              <ClusterCard
                key={cluster.cluster_id}
                cluster={cluster}
                finding={findingByCluster[cluster.cluster_id]}
                selected={selectedCluster === cluster.cluster_id}
                onSelect={() => setSelectedCluster(cluster.cluster_id)}
              />
            ))}
          </div>

          {/* Finding detail */}
          <div className="lg:col-span-2">
            <FindingPanel finding={selectedFinding} />
          </div>
        </div>
      )}
    </div>
  )
}
