import { useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Activity, AlertTriangle, Bot, CheckCircle, ChevronDown, ChevronRight,
  Clock, FileText, GitBranch, Layers, RefreshCw, Shield, Stethoscope, XCircle, Zap,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import toast from 'react-hot-toast'
import PageHeader from '@/components/ui/PageHeader'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useActiveLiveRuns, usePipelineStages, usePipelines, useRunSummary } from '@/hooks/useAgentRuns'
import agentService from '@/services/agentService'
import type { ActiveLiveRun, AgentPipelineRun, AgentStageResult } from '@/types/agent'

// ── Stage metadata ─────────────────────────────────────────────

const STAGE_META: Record<string, { label: string; icon: React.ElementType; description: string }> = {
  ingestion: {
    label: 'Ingestion',
    icon: GitBranch,
    description: 'Validate and enrich test data from PostgreSQL',
  },
  anomaly_detection: {
    label: 'Anomaly Detection',
    icon: AlertTriangle,
    description: 'Compare against baselines, detect regressions and flaky tests',
  },
  root_cause_analysis: {
    label: 'Root Cause Analysis',
    icon: Bot,
    description: 'LangChain ReAct agent investigates each failure',
  },
  summary: {
    label: 'Summary Generation',
    icon: FileText,
    description: 'AI-written run summary and executive report',
  },
  triage: {
    label: 'Defect Triage',
    icon: Zap,
    description: 'Auto-create Jira tickets for high-confidence failures',
  },
  failure_clustering: {
    label: 'Failure Clustering',
    icon: Layers,
    description: 'Semantically group failures to reduce redundant LLM calls',
  },
  flaky_sentinel: {
    label: 'Flaky Sentinel',
    icon: AlertTriangle,
    description: 'Investigate flaky test lifecycles and quarantine candidates',
  },
  test_health: {
    label: 'Test Health',
    icon: Stethoscope,
    description: 'Analyze test code for anti-patterns and automation defects',
  },
  release_risk: {
    label: 'Release Risk',
    icon: Shield,
    description: 'AI go/no-go release recommendation with risk scoring',
  },
}

const STATUS_COLOUR: Record<string, string> = {
  pending: 'text-slate-400',
  running: 'text-blue-400',
  completed: 'text-emerald-400',
  failed: 'text-red-400',
  skipped: 'text-slate-500',
}

const STATUS_BG: Record<string, string> = {
  pending: 'bg-slate-700',
  running: 'bg-blue-900/40 border border-blue-700/40',
  completed: 'bg-emerald-900/20 border border-emerald-700/30',
  failed: 'bg-red-900/20 border border-red-700/30',
  skipped: 'bg-slate-800/60',
}

// ── Sub-components ─────────────────────────────────────────────

function StatusIcon({ status }: { status: string }) {
  if (status === 'completed') return <CheckCircle className="w-4 h-4 text-emerald-400" />
  if (status === 'failed') return <XCircle className="w-4 h-4 text-red-400" />
  if (status === 'running') return <RefreshCw className="w-4 h-4 text-blue-400 animate-spin" />
  if (status === 'skipped') return <ChevronRight className="w-4 h-4 text-slate-500" />
  return <Clock className="w-4 h-4 text-slate-500" />
}

function StageCard({ stage }: { stage: AgentStageResult }) {
  const [open, setOpen] = useState(stage.status === 'failed')
  const meta = STAGE_META[stage.stage_name]
  if (!meta) return null
  const Icon = meta.icon

  const duration =
    stage.started_at && stage.completed_at
      ? Math.round(
          (new Date(stage.completed_at).getTime() - new Date(stage.started_at).getTime()) / 1000,
        )
      : null

  return (
    <div className={`rounded-lg p-3 ${STATUS_BG[stage.status] || 'bg-slate-800'}`}>
      <button
        className="w-full flex items-center gap-3 text-left"
        onClick={() => setOpen(v => !v)}
      >
        <StatusIcon status={stage.status} />
        <div className="p-1.5 rounded-md bg-slate-800/60">
          <Icon className={`w-3.5 h-3.5 ${STATUS_COLOUR[stage.status]}`} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-200">{meta.label}</p>
          <p className="text-xs text-slate-500">{meta.description}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {duration !== null && (
            <span className="text-xs text-slate-500">{duration}s</span>
          )}
          <span className={`text-xs font-mono ${STATUS_COLOUR[stage.status]}`}>
            {stage.status.toUpperCase()}
          </span>
          {open ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />}
        </div>
      </button>

      {open && (stage.result_data || stage.error) && (
        <div className="mt-3 ml-10 space-y-2">
          {stage.result_data && (
            <div className="bg-slate-900/60 rounded p-2 text-xs font-mono text-slate-300">
              {Object.entries(stage.result_data).map(([k, v]) => (
                <div key={k} className="flex gap-2">
                  <span className="text-slate-500">{k}:</span>
                  <span>{String(v)}</span>
                </div>
              ))}
            </div>
          )}
          {stage.error && (
            <div className="bg-red-950/40 border border-red-800/30 rounded p-2 text-xs text-red-300">
              {stage.error}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function PipelineCard({
  pipeline,
  onSelect,
  selected,
}: {
  pipeline: AgentPipelineRun
  onSelect: () => void
  selected: boolean
}) {
  const started = pipeline.started_at ? new Date(pipeline.started_at).toLocaleString() : '—'
  const duration =
    pipeline.started_at && pipeline.completed_at
      ? Math.round(
          (new Date(pipeline.completed_at).getTime() - new Date(pipeline.started_at).getTime()) / 1000,
        )
      : null

  return (
    <button
      onClick={onSelect}
      className={`w-full text-left card p-3 hover:border-slate-600 transition-colors ${
        selected ? 'border-blue-600 bg-blue-950/20' : ''
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <StatusIcon status={pipeline.status} />
        <span className="text-sm font-medium text-slate-200 capitalize">
          {pipeline.workflow_type} pipeline
        </span>
        <span className={`ml-auto text-xs font-mono ${STATUS_COLOUR[pipeline.status]}`}>
          {pipeline.status.toUpperCase()}
        </span>
      </div>
      <p className="text-xs text-slate-500 pl-5">{started}</p>
      {duration !== null && (
        <p className="text-xs text-slate-500 pl-5">Duration: {duration}s</p>
      )}
    </button>
  )
}

function LiveRunCard({ run }: { run: ActiveLiveRun }) {
  const completed = run.passed + run.failed + run.broken
  const progress = run.total > 0 ? (completed / run.total) * 100 : 0

  return (
    <div className="card border border-blue-700/30 bg-blue-950/10">
      <div className="flex items-center gap-2 mb-2">
        <Activity className="w-4 h-4 text-blue-400 animate-pulse" />
        <span className="text-sm font-semibold text-slate-200">Build {run.build_number}</span>
        <span className="ml-auto text-xs bg-blue-900/40 text-blue-400 px-2 py-0.5 rounded-full">
          LIVE
        </span>
      </div>
      {run.current_test && (
        <p className="text-xs text-slate-400 truncate mb-2">
          Running: <span className="text-slate-300">{run.current_test}</span>
        </p>
      )}
      <div className="grid grid-cols-4 gap-2 mb-2 text-center text-xs">
        <div><div className="text-emerald-400 font-mono">{run.passed}</div><div className="text-slate-500">Pass</div></div>
        <div><div className="text-red-400 font-mono">{run.failed}</div><div className="text-slate-500">Fail</div></div>
        <div><div className="text-yellow-400 font-mono">{run.skipped}</div><div className="text-slate-500">Skip</div></div>
        <div><div className="text-slate-200 font-mono">{run.pass_rate}%</div><div className="text-slate-500">Rate</div></div>
      </div>
      <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all"
          style={{ width: `${progress}%` }}
        />
      </div>
      <p className="text-xs text-slate-500 mt-1">{completed}/{run.total} tests run</p>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────

export default function AgentStatusPage() {
  const { runId } = useParams<{ runId?: string }>()
  const [selectedPipeline, setSelectedPipeline] = useState<string | null>(null)
  const [showSummary, setShowSummary] = useState(false)

  const { data: rawPipelines = [], isLoading: pipelinesLoading } = usePipelines(runId)
  // Sort descending by created_at client-side as a defensive guarantee
  const pipelines = [...rawPipelines].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  )
  const { data: stages = [], isLoading: stagesLoading } = usePipelineStages(selectedPipeline)
  const { data: liveRuns = [] } = useActiveLiveRuns()
  const { data: summary } = useRunSummary(
    showSummary && selectedPipeline
      ? pipelines.find((p: AgentPipelineRun) => p.id === selectedPipeline)?.test_run_id ?? null
      : null,
  )

  const _handleTrigger = async (testRunId: string) => {
    try {
      await agentService.triggerPipeline(testRunId)
      toast.success('Pipeline triggered successfully')
    } catch {
      toast.error('Failed to trigger pipeline')
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agent Pipeline"
        subtitle="Multi-agent test analysis: ingestion → anomaly detection → root-cause → summary → triage"
      />

      {/* Live runs */}
      {liveRuns.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">
            Live Executions
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {liveRuns.map((run) => (
              <LiveRunCard key={run.run_id} run={run} />
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pipeline list */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
            Pipeline Runs
          </h3>
          {pipelinesLoading ? (
            <LoadingSpinner size="sm" />
          ) : pipelines.length === 0 ? (
            <p className="text-sm text-slate-500">No pipelines yet. Upload a test report to trigger one.</p>
          ) : (
            pipelines.map((p: AgentPipelineRun) => (
              <PipelineCard
                key={p.id}
                pipeline={p}
                selected={selectedPipeline === p.id}
                onSelect={() => {
                  setSelectedPipeline(p.id)
                  setShowSummary(false)
                }}
              />
            ))
          )}
        </div>

        {/* Stage detail */}
        <div className="lg:col-span-2 space-y-3">
          {!selectedPipeline ? (
            <div className="card flex flex-col items-center justify-center py-16 text-center">
              <Bot className="w-12 h-12 text-slate-600 mb-3" />
              <p className="text-slate-400">Select a pipeline run to see agent stages</p>
            </div>
          ) : stagesLoading ? (
            <div className="flex justify-center py-8"><LoadingSpinner /></div>
          ) : (
            <>
              <div className="flex items-center gap-3 mb-1">
                <h3 className="text-sm font-semibold text-slate-300">Agent Stages</h3>
                <button
                  onClick={() => setShowSummary(v => !v)}
                  className="ml-auto flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300"
                >
                  <FileText className="w-3.5 h-3.5" />
                  {showSummary ? 'Hide report' : 'View AI report'}
                </button>
              </div>

              <div className="space-y-2">
                {stages.map((stage: AgentStageResult) => (
                  <StageCard key={stage.stage_name} stage={stage} />
                ))}
              </div>

              {showSummary && (
                <div className="card mt-4">
                  {!summary ? (
                    <p className="text-sm text-slate-500">No AI summary available yet.</p>
                  ) : (
                    <div className="space-y-4">
                      <div className="bg-slate-800/60 rounded-lg p-3">
                        <h4 className="text-xs font-semibold text-slate-400 uppercase mb-1">Executive Summary</h4>
                        <p className="text-sm text-slate-200 leading-relaxed">{summary.executive_summary}</p>
                      </div>
                      <div className="prose prose-invert prose-sm max-w-none">
                        <ReactMarkdown>{summary.markdown_report}</ReactMarkdown>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
