import { useState } from 'react'
import {
  AlertTriangle, Bot, CheckCircle, ChevronDown, ChevronUp,
  ExternalLink, Loader2, Shield, Zap,
} from 'lucide-react'
import { clsx } from 'clsx'
import toast from 'react-hot-toast'
import { aiService, type AnalysisResult } from '@/services/aiService'
import { confidenceColor } from '@/utils/formatters'

interface Props {
  testCaseId: string
  testName: string
  runId: string
  serviceName?: string
  timestamp?: string
  ocpPodName?: string
  ocpNamespace?: string
  projectKey?: string
}

type Stage = 'idle' | 'fetching_stacktrace' | 'querying_splunk' | 'checking_flakiness' | 'analyzing_ocp' | 'generating' | 'done' | 'error'

const STAGE_LABELS: Record<Stage, string> = {
  idle: '',
  fetching_stacktrace: 'Fetching stack trace…',
  querying_splunk: 'Querying Splunk logs…',
  checking_flakiness: 'Checking flakiness history…',
  analyzing_ocp: 'Analysing OpenShift pod events…',
  generating: 'Generating root cause analysis…',
  done: '',
  error: '',
}

const STAGES: Stage[] = ['fetching_stacktrace', 'querying_splunk', 'checking_flakiness', 'analyzing_ocp', 'generating']

const CATEGORY_STYLES: Record<string, string> = {
  PRODUCT_BUG:       'bg-red-900/40 text-red-300 border-red-700/50',
  INFRASTRUCTURE:    'bg-orange-900/40 text-orange-300 border-orange-700/50',
  TEST_DATA:         'bg-amber-900/40 text-amber-300 border-amber-700/50',
  AUTOMATION_DEFECT: 'bg-purple-900/40 text-purple-300 border-purple-700/50',
  FLAKY:             'bg-pink-900/40 text-pink-300 border-pink-700/50',
  UNKNOWN:           'bg-slate-800 text-slate-400 border-slate-600',
}

export default function AIAnalysisPanel({
  testCaseId, testName, runId, serviceName, timestamp, ocpPodName, ocpNamespace, projectKey,
}: Props) {
  const [stage, setStage]       = useState<Stage>('idle')
  const [result, setResult]     = useState<AnalysisResult | null>(null)
  const [jiraUrl, setJiraUrl]   = useState<string | null>(null)
  const [creatingJira, setCreatingJira] = useState(false)
  const [expanded, setExpanded] = useState(true)

  const simulateStages = async (): Promise<void> => {
    for (const s of STAGES) {
      setStage(s)
      await new Promise(r => setTimeout(r, 700))
    }
  }

  const handleAnalyze = async () => {
    setStage('fetching_stacktrace')
    setResult(null)
    setJiraUrl(null)
    try {
      const [analysis] = await Promise.all([
        aiService.analyze({
          test_case_id: testCaseId,
          service_name: serviceName,
          timestamp,
          ocp_pod_name: ocpPodName,
          ocp_namespace: ocpNamespace,
        }),
        simulateStages(),
      ])
      setResult(analysis)
      setStage('done')
    } catch {
      setStage('error')
      toast.error('AI analysis failed. Check backend logs.')
    }
  }

  const handleCreateJira = async () => {
    if (!result || !projectKey) return
    setCreatingJira(true)
    try {
      const resp = await aiService.createJiraTicket({
        project_key: projectKey,
        test_case_id: testCaseId,
        test_name: testName,
        run_id: runId,
        ai_summary: result.root_cause_summary,
        recommended_action: result.recommended_actions[0] ?? '',
      })
      setJiraUrl(resp.ticket_url)
      toast.success(`Jira ticket created: ${resp.ticket_key}`)
    } catch {
      toast.error('Failed to create Jira ticket')
    } finally {
      setCreatingJira(false)
    }
  }

  // ── Idle state ─────────────────────────────────────────────
  if (stage === 'idle') {
    return (
      <div className="card flex flex-col items-center gap-4 py-10">
        <div className="p-4 bg-blue-600/10 rounded-2xl">
          <Bot className="h-10 w-10 text-blue-400" />
        </div>
        <div className="text-center">
          <p className="font-semibold text-slate-200">AI Root Cause Analysis</p>
          <p className="text-sm text-slate-400 mt-1 max-w-xs">
            Powered by {import.meta.env.VITE_LLM_PROVIDER || 'Ollama (local)'} — no data leaves your network
          </p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={handleAnalyze}>
          <Zap className="h-4 w-4" />
          Analyse Root Cause
        </button>
      </div>
    )
  }

  // ── Loading state ──────────────────────────────────────────
  if (stage !== 'done' && stage !== 'error') {
    return (
      <div className="card">
        <div className="flex items-center gap-3 mb-5">
          <Loader2 className="h-5 w-5 text-blue-400 animate-spin" />
          <p className="font-semibold text-slate-200">Investigating…</p>
        </div>
        <div className="space-y-2">
          {STAGES.map((s) => {
            const currentIdx = STAGES.indexOf(stage)
            const stageIdx   = STAGES.indexOf(s)
            const isDone     = stageIdx < currentIdx
            const isActive   = s === stage
            return (
              <div key={s} className={clsx(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all',
                isActive && 'bg-blue-600/10 border border-blue-600/30',
                isDone && 'opacity-50',
              )}>
                {isDone
                  ? <CheckCircle className="h-4 w-4 text-emerald-400 flex-shrink-0" />
                  : isActive
                    ? <Loader2 className="h-4 w-4 text-blue-400 animate-spin flex-shrink-0" />
                    : <div className="h-4 w-4 rounded-full border border-slate-700 flex-shrink-0" />}
                <span className={isActive ? 'text-blue-300' : 'text-slate-400'}>{STAGE_LABELS[s]}</span>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  // ── Error state ────────────────────────────────────────────
  if (stage === 'error') {
    return (
      <div className="card border-red-800/50">
        <div className="flex items-center gap-3 mb-3">
          <AlertTriangle className="h-5 w-5 text-red-400" />
          <p className="font-semibold text-red-300">Analysis Failed</p>
        </div>
        <p className="text-sm text-slate-400 mb-4">The AI agent encountered an error. Check that your LLM (Ollama) is running.</p>
        <button className="btn-secondary text-sm" onClick={() => setStage('idle')}>Try Again</button>
      </div>
    )
  }

  // ── Result state ───────────────────────────────────────────
  if (!result) return null

  const categoryStyle = CATEGORY_STYLES[result.failure_category] ?? CATEGORY_STYLES.UNKNOWN
  const confColor = confidenceColor(result.confidence_score)

  return (
    <div className="card space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-600/10 rounded-xl">
            <Bot className="h-5 w-5 text-blue-400" />
          </div>
          <div>
            <p className="font-semibold text-slate-200">AI Triage Result</p>
            <p className="text-xs text-slate-500">{result.llm_provider} · {result.llm_model}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className={clsx('text-2xl font-bold tabular-nums', confColor)}>{result.confidence_score}%</p>
            <p className="text-[10px] text-slate-500 uppercase tracking-wider">Confidence</p>
          </div>
          <button onClick={() => setExpanded(x => !x)} className="btn-ghost p-1">
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Category + flags */}
      <div className="flex flex-wrap gap-2">
        <span className={clsx('badge border', categoryStyle)}>{result.failure_category.replace('_', ' ')}</span>
        {result.is_flaky && (
          <span className="badge bg-pink-900/40 text-pink-300 border border-pink-700/50">
            ⚠ High Flakiness
          </span>
        )}
        {result.backend_error_found && (
          <span className="badge bg-orange-900/40 text-orange-300 border border-orange-700/50">
            Backend Error Found
          </span>
        )}
        {result.pod_issue_found && (
          <span className="badge bg-red-900/40 text-red-300 border border-red-700/50">
            OCP Pod Issue
          </span>
        )}
        {result.requires_human_review && (
          <span className="badge bg-amber-900/40 text-amber-300 border border-amber-700/50">
            ⏳ Pending Human Review
          </span>
        )}
      </div>

      {expanded && (
        <>
          {/* Root cause summary */}
          <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl p-4">
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">Root Cause Summary</p>
            <p className="text-sm text-slate-200 leading-relaxed">{result.root_cause_summary}</p>
          </div>

          {/* Recommended actions */}
          {result.recommended_actions.length > 0 && (
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">Recommended Actions</p>
              <ul className="space-y-1.5">
                {result.recommended_actions.map((action, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                    <CheckCircle className="h-4 w-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                    {action}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Evidence references */}
          {result.evidence_references.length > 0 && (
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">Evidence</p>
              <div className="space-y-2">
                {result.evidence_references.map((ev, i) => (
                  <div key={i} className="bg-slate-800 rounded-lg px-3 py-2 text-xs">
                    <span className="text-blue-400 font-medium uppercase mr-2">{ev.source}</span>
                    <span className="text-slate-300">{ev.excerpt}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3 pt-1">
        <button
          className="btn-secondary text-sm flex items-center gap-2"
          onClick={() => setStage('idle')}
        >
          <Zap className="h-3.5 w-3.5" />
          Re-analyse
        </button>

        {jiraUrl ? (
          <a
            href={jiraUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-primary text-sm flex items-center gap-2"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            View Jira Ticket
          </a>
        ) : (
          <button
            className="btn-primary text-sm flex items-center gap-2 disabled:opacity-50"
            onClick={handleCreateJira}
            disabled={creatingJira || !projectKey || result.requires_human_review}
            title={result.requires_human_review ? 'Low confidence — manual review required before creating ticket' : ''}
          >
            {creatingJira
              ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Creating…</>
              : <><Shield className="h-3.5 w-3.5" /> Create Jira Defect</>
            }
          </button>
        )}
      </div>
    </div>
  )
}
