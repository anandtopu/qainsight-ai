import { useState } from 'react'
import { TrendingUp } from 'lucide-react'
import PageHeader from '@/components/ui/PageHeader'
import TrendChart from '@/components/charts/TrendChart'
import EmptyState from '@/components/ui/EmptyState'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useTrendData } from '@/hooks/useMetrics'
import { useProjectStore } from '@/store/projectStore'
import { clsx } from 'clsx'

const PERIODS = [
  { label: '7d',  days: 7 },
  { label: '14d', days: 14 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
]

export default function TrendsPage() {
  const [days, setDays] = useState(30)
  const project = useProjectStore(s => s.activeProject)
  const { data: trends, isLoading } = useTrendData(days)

  if (!project) {
    return (
      <EmptyState
        icon={<TrendingUp className="h-10 w-10" />}
        title="No project selected"
        description="Select a project from the top bar to view trend data"
      />
    )
  }

  const trendData = trends?.data ?? []

  const totalPassed  = trendData.reduce((s: number, d: any) => s + d.passed,  0)
  const totalFailed  = trendData.reduce((s: number, d: any) => s + d.failed,  0)
  const totalSkipped = trendData.reduce((s: number, d: any) => s + d.skipped, 0)
  const totalBroken  = trendData.reduce((s: number, d: any) => s + d.broken,  0)
  const avgPassRate  = trendData.length > 0
    ? (trendData.reduce((s: number, d: any) => s + d.pass_rate, 0) / trendData.length).toFixed(1)
    : '—'

  return (
    <div className="space-y-6">
      <PageHeader
        title="Trends"
        subtitle={`Historical pass/fail rates for ${project.name}`}
        actions={
          <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
            {PERIODS.map(({ label, days: d }) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={clsx(
                  'px-3 py-1 rounded-md text-sm font-medium transition-colors',
                  days === d ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-100',
                )}
              >
                {label}
              </button>
            ))}
          </div>
        }
      />

      {/* Summary strip */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[
          { label: 'Avg Pass Rate', value: `${avgPassRate}%`, color: 'text-emerald-400' },
          { label: 'Total Passed',  value: totalPassed,       color: 'text-emerald-400' },
          { label: 'Total Failed',  value: totalFailed,       color: 'text-red-400'     },
          { label: 'Total Skipped', value: totalSkipped,      color: 'text-amber-400'   },
          { label: 'Total Broken',  value: totalBroken,       color: 'text-orange-400'  },
        ].map(({ label, value, color }) => (
          <div key={label} className="card py-3">
            <p className="text-xs text-slate-500 uppercase tracking-wider">{label}</p>
            <p className={clsx('text-2xl font-bold tabular-nums mt-1', color)}>{value}</p>
          </div>
        ))}
      </div>

      {/* Charts */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>
      ) : trendData.length === 0 ? (
        <EmptyState
          icon={<TrendingUp className="h-8 w-8" />}
          title="No trend data yet"
          description="Run some tests to see pass/fail trends over time"
        />
      ) : (
        <div className="space-y-4">
          <div className="card">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Pass / Fail / Skip — Daily Breakdown</h3>
            <TrendChart data={trendData} type="bar" height={300} />
          </div>

          <div className="card">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Pass Rate Trend (%)</h3>
            <TrendChart data={trendData} type="line" height={240} />
          </div>

          <div className="card">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Cumulative Test Volume</h3>
            <TrendChart data={trendData} type="area" height={240} />
          </div>
        </div>
      )}
    </div>
  )
}
