import { useState } from 'react'
import { AlertTriangle, Bug, CheckCircle, Clock, TrendingUp, Zap } from 'lucide-react'
import MetricCard from '@/components/ui/MetricCard'
import TrendChart from '@/components/charts/TrendChart'
import PageHeader from '@/components/ui/PageHeader'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useDashboardSummary, useTrendData } from '@/hooks/useMetrics'
import { ALL_PROJECTS_ID, useProjectStore } from '@/store/projectStore'
import { formatDuration } from '@/utils/formatters'
import { clsx } from 'clsx'

const TIME_OPTIONS = [7, 14, 30, 90]

const READINESS_STYLES = {
  GREEN: 'bg-emerald-900/40 text-emerald-300 border-emerald-700/50',
  AMBER: 'bg-amber-900/40 text-amber-300 border-amber-700/50',
  RED:   'bg-red-900/40 text-red-300 border-red-700/50',
}

export default function OverviewPage() {
  const [days, setDays] = useState(7)
  const project = useProjectStore(s => s.activeProject)
  const activeProjectId = useProjectStore(s => s.activeProjectId)
  const isAllProjects = activeProjectId === ALL_PROJECTS_ID

  const { data: summary, isLoading: summaryLoading } = useDashboardSummary(days)
  const { data: trends,  isLoading: trendsLoading  } = useTrendData(days)

  if (!project && !isAllProjects) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center">
        <TrendingUp className="h-12 w-12 text-slate-600 mb-3" />
        <p className="text-slate-400 font-medium">Select a project to view the dashboard</p>
        <p className="text-slate-500 text-sm mt-1">Use the project selector in the top bar</p>
      </div>
    )
  }

  const projectLabel = project?.name ?? 'All Projects'
  const readiness = summary?.release_readiness
  const trendData = (trends?.data ?? []).map((point) => ({
    ...point,
    total: point.total ?? point.passed + point.failed + point.skipped + (point.broken ?? 0),
  }))

  return (
    <div className="space-y-6">
      <PageHeader
        title="Executive Dashboard"
        subtitle={projectLabel}
        actions={
          <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
            {TIME_OPTIONS.map(d => (
              <button
                key={d}
                className={clsx(
                  'px-3 py-1 rounded-md text-sm font-medium transition-colors',
                  days === d ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-100',
                )}
                onClick={() => setDays(d)}
              >
                {d}d
              </button>
            ))}
          </div>
        }
      />

      {/* Release Readiness banner */}
      {readiness && (
        <div className={clsx('flex items-center gap-3 px-5 py-3 rounded-xl border', READINESS_STYLES[readiness as keyof typeof READINESS_STYLES])}>
          {readiness === 'GREEN' && <CheckCircle className="h-5 w-5" />}
          {readiness === 'AMBER' && <AlertTriangle className="h-5 w-5" />}
          {readiness === 'RED'   && <Bug className="h-5 w-5" />}
          <div>
            <span className="font-semibold">Release Readiness: {readiness}</span>
            <span className="text-sm ml-2 opacity-75">
              {readiness === 'GREEN' && '✓ All quality gates passing'}
              {readiness === 'AMBER' && '⚠ Some quality criteria need attention'}
              {readiness === 'RED'   && '✗ Critical issues must be resolved before release'}
            </span>
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard
          title="Total Executions"
          metric={summary?.total_executions_7d}
          icon={<TrendingUp className="h-5 w-5" />}
          accentColor="blue"
          loading={summaryLoading}
        />
        <MetricCard
          title="Avg Pass Rate"
          metric={summary ? { ...summary.avg_pass_rate_7d, value: `${summary.avg_pass_rate_7d?.value ?? 0}%` } : undefined}
          icon={<CheckCircle className="h-5 w-5" />}
          accentColor="green"
          loading={summaryLoading}
        />
        <MetricCard
          title="Active Defects"
          metric={summary?.active_defects}
          icon={<Bug className="h-5 w-5" />}
          accentColor="red"
          loading={summaryLoading}
        />
        <MetricCard
          title="Flaky Tests"
          metric={summary?.flaky_test_count}
          icon={<AlertTriangle className="h-5 w-5" />}
          accentColor="amber"
          loading={summaryLoading}
        />
        <MetricCard
          title="New Failures (24h)"
          metric={summary?.new_failures_24h}
          icon={<Zap className="h-5 w-5" />}
          accentColor="red"
          loading={summaryLoading}
        />
        <MetricCard
          title="Avg Run Duration"
          metric={summary ? { ...summary.avg_duration_ms, value: formatDuration(summary.avg_duration_ms?.value as number) } : undefined}
          icon={<Clock className="h-5 w-5" />}
          accentColor="purple"
          loading={summaryLoading}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="card">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">Execution Trend — Pass / Fail / Skip</h3>
          {trendsLoading
            ? <div className="flex items-center justify-center h-64"><LoadingSpinner /></div>
            : <TrendChart data={trendData} type="line" />
          }
        </div>
        <div className="card">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">Total Test Automation Growth</h3>
          {trendsLoading
            ? <div className="flex items-center justify-center h-64"><LoadingSpinner /></div>
            : <TrendChart data={trendData} type="area" />
          }
        </div>
      </div>
    </div>
  )
}
