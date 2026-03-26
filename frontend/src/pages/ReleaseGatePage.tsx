import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  AlertTriangle, CheckCircle, Shield, XCircle, Zap,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { clsx } from 'clsx'
import PageHeader from '@/components/ui/PageHeader'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import EmptyState from '@/components/ui/EmptyState'
import { useReleaseDecision } from '@/hooks/useDeepInvestigation'
import { deepInvestigationService } from '@/services/deepInvestigationService'
import { useRuns } from '@/hooks/useRuns'

type Recommendation = 'GO' | 'NO_GO' | 'CONDITIONAL_GO'

const REC_CONFIG: Record<Recommendation, { label: string; colour: string; bg: string; icon: React.ElementType }> = {
  GO:              { label: 'GO',              colour: 'text-emerald-400', bg: 'bg-emerald-900/20 border-emerald-700/30', icon: CheckCircle },
  NO_GO:           { label: 'NO GO',           colour: 'text-red-400',     bg: 'bg-red-900/20 border-red-700/30',         icon: XCircle     },
  CONDITIONAL_GO:  { label: 'CONDITIONAL GO',  colour: 'text-amber-400',   bg: 'bg-amber-900/20 border-amber-700/30',     icon: AlertTriangle },
}

function RiskGauge({ score }: { score: number }) {
  const colour = score >= 70 ? '#f87171' : score >= 40 ? '#fbbf24' : '#34d399'
  const pct = Math.min(100, Math.max(0, score))
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="120" height="70" viewBox="0 0 120 70">
        {/* Background arc */}
        <path d="M 10 65 A 50 50 0 0 1 110 65" fill="none" stroke="#334155" strokeWidth="10" strokeLinecap="round" />
        {/* Filled arc */}
        <path
          d="M 10 65 A 50 50 0 0 1 110 65"
          fill="none"
          stroke={colour}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${(pct / 100) * 157} 157`}
        />
        <text x="60" y="60" textAnchor="middle" fill="white" fontSize="22" fontWeight="bold">{score}</text>
      </svg>
      <p className="text-xs text-slate-500">Risk Score</p>
    </div>
  )
}

export default function ReleaseGatePage() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const { data: decision, isLoading, error, mutate } = useReleaseDecision(runId ?? null)
  const [overrideMode, setOverrideMode] = useState(false)
  const [overrideRec, setOverrideRec] = useState<Recommendation>('GO')
  const [overrideReason, setOverrideReason] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const { data: recentRuns } = useRuns({ page: 1, size: 1 })
  useEffect(() => {
    if (!runId && recentRuns?.items?.[0]?.id) {
      navigate(`/release-gate/${recentRuns.items[0].id}`, { replace: true })
    }
  }, [runId, recentRuns, navigate])

  if (!runId) {
    return (
      <EmptyState
        icon={<Shield className="h-10 w-10" />}
        title="No run selected"
        description="Navigate to a test run to see the release gate decision."
      />
    )
  }

  if (isLoading) {
    return <div className="flex justify-center py-16"><LoadingSpinner size="lg" /></div>
  }

  if (error || !decision) {
    return (
      <EmptyState
        icon={<Shield className="h-10 w-10" />}
        title="No release decision"
        description="Trigger deep investigation on this run to generate a release recommendation."
      />
    )
  }

  const cfg = REC_CONFIG[decision.recommendation as Recommendation] ?? REC_CONFIG.CONDITIONAL_GO
  const Icon = cfg.icon

  const handleOverride = async () => {
    if (!overrideReason.trim()) {
      toast.error('Please provide a reason for the override')
      return
    }
    setSubmitting(true)
    try {
      await deepInvestigationService.overrideRelease(runId, overrideRec, overrideReason)
      toast.success('Release decision overridden')
      setOverrideMode(false)
      setOverrideReason('')
      await mutate()
    } catch {
      toast.error('Override failed — QA Lead role required')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Release Gate"
        subtitle={`Build ${decision.build_number ?? runId} — AI-powered go/no-go assessment`}
      />

      {/* Main decision banner */}
      <div className={clsx('card border rounded-xl p-6 flex items-center gap-6', cfg.bg)}>
        <Icon className={clsx('w-16 h-16 shrink-0', cfg.colour)} />
        <div className="flex-1 min-w-0">
          <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Recommendation</p>
          <p className={clsx('text-4xl font-black tracking-tight', cfg.colour)}>{cfg.label}</p>
          {decision.pass_rate != null && (
            <p className="text-sm text-slate-400 mt-1">Pass rate: {decision.pass_rate.toFixed(1)}%</p>
          )}
        </div>
        <RiskGauge score={decision.risk_score} />
      </div>

      {/* Override badge */}
      {decision.human_override && (
        <div className="card border border-amber-700/30 bg-amber-900/10 py-3">
          <p className="text-xs text-amber-400 uppercase tracking-wider mb-1">Human Override Applied</p>
          <p className="text-sm text-slate-300">{decision.human_override}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Blocking issues */}
        {decision.blocking_issues.length > 0 && (
          <div className="card">
            <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
              <XCircle className="w-4 h-4 text-red-400" />
              Blocking Issues
            </h3>
            <ul className="space-y-2">
              {decision.blocking_issues.map((issue, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                  <span className="text-red-400 mt-0.5 shrink-0">✕</span>
                  {issue}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Conditions for go */}
        {decision.conditions_for_go.length > 0 && (
          <div className="card">
            <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" />
              Conditions for GO
            </h3>
            <ul className="space-y-2">
              {decision.conditions_for_go.map((cond, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                  <span className="text-amber-400 mt-0.5 shrink-0">→</span>
                  {cond}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Reasoning */}
      {decision.reasoning && (
        <div className="card">
          <h3 className="text-sm font-semibold text-slate-200 mb-2">AI Reasoning</h3>
          <p className="text-sm text-slate-300 leading-relaxed">{decision.reasoning}</p>
        </div>
      )}

      {/* Override section */}
      <div className="card">
        <div className="flex items-center gap-3 mb-3">
          <Shield className="w-4 h-4 text-slate-400" />
          <h3 className="text-sm font-semibold text-slate-200">QA Lead Override</h3>
          {!overrideMode && (
            <button
              onClick={() => setOverrideMode(true)}
              className="ml-auto text-xs text-blue-400 hover:text-blue-300"
            >
              Override decision
            </button>
          )}
        </div>
        {overrideMode && (
          <div className="space-y-3">
            <div className="flex gap-2">
              {(['GO', 'CONDITIONAL_GO', 'NO_GO'] as Recommendation[]).map(rec => (
                <button
                  key={rec}
                  onClick={() => setOverrideRec(rec)}
                  className={clsx(
                    'px-3 py-1.5 rounded text-xs font-medium transition-colors',
                    overrideRec === rec
                      ? clsx(REC_CONFIG[rec].colour, 'bg-slate-700')
                      : 'text-slate-400 hover:text-slate-200',
                  )}
                >
                  {REC_CONFIG[rec].label}
                </button>
              ))}
            </div>
            <textarea
              value={overrideReason}
              onChange={e => setOverrideReason(e.target.value)}
              placeholder="Reason for override (required)…"
              rows={3}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 resize-none"
            />
            <div className="flex gap-2">
              <button
                onClick={handleOverride}
                disabled={submitting}
                className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg disabled:opacity-50"
              >
                {submitting ? 'Saving…' : 'Apply Override'}
              </button>
              <button
                onClick={() => { setOverrideMode(false); setOverrideReason('') }}
                className="px-4 py-1.5 text-slate-400 hover:text-slate-200 text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
