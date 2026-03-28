import { useEffect, useState } from 'react'
import {
  Download, Mail, Plus, Settings2, TrendingUp, X,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  PieChart, Pie, Cell,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { clsx } from 'clsx'
import toast from 'react-hot-toast'
import PageHeader from '@/components/ui/PageHeader'
import EmptyState from '@/components/ui/EmptyState'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useTrendData } from '@/hooks/useMetrics'
import { useProjectStore } from '@/store/projectStore'
import type { TrendPoint } from '@/types/metrics'
import { postData } from '@/services/http'

// ── Constants ──────────────────────────────────────────────────────────────

const PERIODS = [
  { label: '7d',  days: 7 },
  { label: '14d', days: 14 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
]

const TOOLTIP_STYLE = {
  backgroundColor: '#1e293b', border: '1px solid #334155',
  borderRadius: '8px', color: '#e2e8f0', fontSize: '12px',
}
const AXIS_TICK = { fill: '#64748b', fontSize: 11 }

// ── Chart catalog ──────────────────────────────────────────────────────────

interface ChartDef {
  id: string
  label: string
  description: string
  defaultEnabled: boolean
}

const CHART_CATALOG: ChartDef[] = [
  { id: 'daily_breakdown',   label: 'Daily Breakdown',    description: 'Stacked bar of passed/failed/skipped per day',  defaultEnabled: true  },
  { id: 'pass_rate_trend',   label: 'Pass Rate Trend',    description: 'Daily pass rate % line chart',                  defaultEnabled: true  },
  { id: 'cumulative_volume', label: 'Cumulative Volume',  description: 'Total test volume growth area chart',           defaultEnabled: true  },
  { id: 'failure_rate',      label: 'Failure Rate',       description: 'Daily failure rate % over time',               defaultEnabled: false },
  { id: 'broken_trend',      label: 'Broken Tests',       description: 'Broken test count trend bar chart',            defaultEnabled: false },
  { id: 'skipped_trend',     label: 'Skipped Trend',      description: 'Skipped test count trend over time',           defaultEnabled: false },
  { id: 'status_pie',        label: 'Status Distribution',description: 'Pie chart of overall status distribution',     defaultEnabled: false },
]

const STORAGE_KEY = 'qainsight_trend_charts'

function loadEnabledCharts(): string[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) return JSON.parse(stored)
  } catch (_e) {
    // ignore parse errors — fall through to defaults
  }
  return CHART_CATALOG.filter(c => c.defaultEnabled).map(c => c.id)
}

function saveEnabledCharts(ids: string[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids))
  } catch (_e) {
    // ignore storage errors (e.g. private browsing quota)
  }
}

// ── Individual chart components ────────────────────────────────────────────

interface ChartProps { data: TrendPoint[]; height?: number }

function DailyBreakdownChart({ data, height = 300 }: ChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} barSize={18} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
        <XAxis dataKey="date" axisLine={false} tickLine={false} tick={AXIS_TICK} dy={8} />
        <YAxis axisLine={false} tickLine={false} tick={AXIS_TICK} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Legend iconType="circle" wrapperStyle={{ paddingTop: 12, fontSize: 12 }} />
        <Bar dataKey="passed"  stackId="a" fill="#10b981" name="Passed"  />
        <Bar dataKey="failed"  stackId="a" fill="#ef4444" name="Failed"  />
        <Bar dataKey="skipped" stackId="a" fill="#f59e0b" name="Skipped" />
        <Bar dataKey="broken"  stackId="a" fill="#f97316" name="Broken"  radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function PassRateTrendChart({ data, height = 240 }: ChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
        <XAxis dataKey="date" axisLine={false} tickLine={false} tick={AXIS_TICK} dy={8} />
        <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={AXIS_TICK} unit="%" />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => [`${v}%`, 'Pass Rate']} />
        <Line type="monotone" dataKey="pass_rate" stroke="#10b981" strokeWidth={2} dot={false} activeDot={{ r: 4 }} name="Pass Rate %" />
      </LineChart>
    </ResponsiveContainer>
  )
}

function CumulativeVolumeChart({ data, height = 240 }: ChartProps) {
  const derived = data.map(d => ({
    ...d,
    total: d.passed + d.failed + d.skipped + d.broken,
  }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={derived} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
        <defs>
          <linearGradient id="totalGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}   />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
        <XAxis dataKey="date" axisLine={false} tickLine={false} tick={AXIS_TICK} dy={8} />
        <YAxis axisLine={false} tickLine={false} tick={AXIS_TICK} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Area type="monotone" dataKey="total"  stroke="#3b82f6" fill="url(#totalGrad)" strokeWidth={2} name="Total Tests" />
        <Area type="monotone" dataKey="passed" stroke="#10b981" fill="transparent"    strokeWidth={1.5} name="Passed" />
      </AreaChart>
    </ResponsiveContainer>
  )
}

function FailureRateChart({ data, height = 240 }: ChartProps) {
  const derived = data.map(d => {
    const total = d.passed + d.failed + d.skipped + d.broken
    return { ...d, failure_rate: total > 0 ? Number(((d.failed + d.broken) / total * 100).toFixed(1)) : 0 }
  })
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={derived} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
        <XAxis dataKey="date" axisLine={false} tickLine={false} tick={AXIS_TICK} dy={8} />
        <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={AXIS_TICK} unit="%" />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => [`${v}%`, 'Failure Rate']} />
        <Line type="monotone" dataKey="failure_rate" stroke="#ef4444" strokeWidth={2} dot={false} activeDot={{ r: 4 }} name="Failure Rate %" />
      </LineChart>
    </ResponsiveContainer>
  )
}

function BrokenTrendChart({ data, height = 240 }: ChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} barSize={18} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
        <XAxis dataKey="date" axisLine={false} tickLine={false} tick={AXIS_TICK} dy={8} />
        <YAxis axisLine={false} tickLine={false} tick={AXIS_TICK} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Bar dataKey="broken" fill="#f97316" name="Broken Tests" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function SkippedTrendChart({ data, height = 240 }: ChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
        <XAxis dataKey="date" axisLine={false} tickLine={false} tick={AXIS_TICK} dy={8} />
        <YAxis axisLine={false} tickLine={false} tick={AXIS_TICK} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Line type="monotone" dataKey="skipped" stroke="#f59e0b" strokeWidth={2} dot={false} activeDot={{ r: 4 }} name="Skipped" strokeDasharray="4 2" />
      </LineChart>
    </ResponsiveContainer>
  )
}

function StatusPieChart({ data, height = 240 }: ChartProps) {
  const totals = data.reduce(
    (acc, d) => ({
      passed:  acc.passed  + d.passed,
      failed:  acc.failed  + d.failed,
      skipped: acc.skipped + d.skipped,
      broken:  acc.broken  + (d.broken ?? 0),
    }),
    { passed: 0, failed: 0, skipped: 0, broken: 0 },
  )
  const pieData = [
    { name: 'Passed',  value: totals.passed,  fill: '#10b981' },
    { name: 'Failed',  value: totals.failed,  fill: '#ef4444' },
    { name: 'Skipped', value: totals.skipped, fill: '#f59e0b' },
    { name: 'Broken',  value: totals.broken,  fill: '#f97316' },
  ].filter(d => d.value > 0)

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={pieData} dataKey="value" cx="50%" cy="50%" outerRadius={90} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
          {pieData.map((entry) => <Cell key={entry.name} fill={entry.fill} />)}
        </Pie>
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  )
}

function renderChart(id: string, data: TrendPoint[]) {
  switch (id) {
    case 'daily_breakdown':   return <DailyBreakdownChart data={data} />
    case 'pass_rate_trend':   return <PassRateTrendChart data={data} />
    case 'cumulative_volume': return <CumulativeVolumeChart data={data} />
    case 'failure_rate':      return <FailureRateChart data={data} />
    case 'broken_trend':      return <BrokenTrendChart data={data} />
    case 'skipped_trend':     return <SkippedTrendChart data={data} />
    case 'status_pie':        return <StatusPieChart data={data} />
    default: return null
  }
}

// ── Email modal ────────────────────────────────────────────────────────────

interface EmailModalProps {
  onClose: () => void
  projectId: string
  days: number
  enabledCharts: string[]
}

function EmailModal({ onClose, projectId, days, enabledCharts }: EmailModalProps) {
  const [email, setEmail] = useState('')
  const [sending, setSending] = useState(false)

  async function handleSend() {
    if (!email.trim()) { toast.error('Enter a recipient email'); return }
    setSending(true)
    try {
      await postData('/api/v1/reports/email-trends', {
        project_id: projectId,
        days,
        recipient_email: email.trim(),
        chart_ids: enabledCharts,
      })
      toast.success('Report sent successfully')
      onClose()
    } catch {
      toast.error('Failed to send report — check SMTP settings')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-slate-100">Email Trends Report</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200"><X className="h-4 w-4" /></button>
        </div>
        <p className="text-sm text-slate-400 mb-4">
          Send a snapshot of the current trend data ({days}-day period, {enabledCharts.length} chart{enabledCharts.length !== 1 ? 's' : ''}) to an email address.
        </p>
        <label className="block text-xs text-slate-400 mb-1">Recipient Email</label>
        <input
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          placeholder="you@example.com"
          className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 mb-4"
          onKeyDown={e => e.key === 'Enter' && handleSend()}
        />
        <div className="flex gap-3 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200">Cancel</button>
          <button
            onClick={handleSend}
            disabled={sending}
            className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg font-medium flex items-center gap-2"
          >
            {sending ? <LoadingSpinner size="sm" /> : <Mail className="h-4 w-4" />}
            {sending ? 'Sending…' : 'Send Report'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Chart picker modal ─────────────────────────────────────────────────────

interface ChartPickerProps {
  enabled: string[]
  onToggle: (id: string) => void
  onClose: () => void
}

function ChartPickerModal({ enabled, onToggle, onClose }: ChartPickerProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-lg shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-slate-100">Customize Charts</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200"><X className="h-4 w-4" /></button>
        </div>
        <p className="text-sm text-slate-400 mb-4">Select which charts to display on the Trends page.</p>
        <div className="space-y-2">
          {CHART_CATALOG.map(chart => (
            <div
              key={chart.id}
              className={clsx(
                'flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                enabled.includes(chart.id)
                  ? 'border-blue-500/50 bg-blue-500/10'
                  : 'border-slate-700 bg-slate-800/50 hover:border-slate-600',
              )}
              onClick={() => onToggle(chart.id)}
            >
              <div className={clsx(
                'h-4 w-4 rounded border-2 flex items-center justify-center flex-shrink-0',
                enabled.includes(chart.id) ? 'border-blue-500 bg-blue-500' : 'border-slate-600',
              )}>
                {enabled.includes(chart.id) && (
                  <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 12 12">
                    <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </div>
              <div>
                <p className="text-sm font-medium text-slate-200">{chart.label}</p>
                <p className="text-xs text-slate-500">{chart.description}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 flex justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium">Done</button>
        </div>
      </div>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────

const PRINT_CHART_WIDTH = 680

export default function TrendsPage() {
  const [days, setDays]           = useState(30)
  const [enabledCharts, setEnabled] = useState<string[]>(loadEnabledCharts)
  const [showPicker, setShowPicker] = useState(false)
  const [showEmail, setShowEmail]   = useState(false)
  const project   = useProjectStore(s => s.activeProject)
  const projectId = useProjectStore(s => s.activeProjectId)
  const { data: trends, isLoading } = useTrendData(days)

  useEffect(() => { saveEnabledCharts(enabledCharts) }, [enabledCharts])

  // beforeprint fires at exactly the right moment — before the browser renders
  // the print layout. We set explicit pixel widths on Recharts SVGs so they
  // don't collapse to 0 when @media print reflows the page.
  useEffect(() => {
    function onBeforePrint() {
      document.querySelectorAll<HTMLElement>('.recharts-responsive-container').forEach(el => {
        el.dataset.printOrigW = el.style.width
        el.style.width = `${PRINT_CHART_WIDTH}px`
        el.style.minWidth = `${PRINT_CHART_WIDTH}px`
      })
      document.querySelectorAll<SVGElement>('.recharts-surface').forEach(svg => {
        svg.dataset.printOrigW = svg.getAttribute('width') ?? ''
        svg.setAttribute('width', String(PRINT_CHART_WIDTH))
      })
    }
    function onAfterPrint() {
      document.querySelectorAll<HTMLElement>('.recharts-responsive-container').forEach(el => {
        el.style.width = el.dataset.printOrigW ?? ''
        el.style.minWidth = ''
        delete el.dataset.printOrigW
      })
      document.querySelectorAll<SVGElement>('.recharts-surface').forEach(svg => {
        const orig = svg.dataset.printOrigW ?? ''
        if (orig) svg.setAttribute('width', orig)
        else svg.removeAttribute('width')
        delete svg.dataset.printOrigW
      })
      window.dispatchEvent(new Event('resize'))
    }
    window.addEventListener('beforeprint', onBeforePrint)
    window.addEventListener('afterprint', onAfterPrint)
    return () => {
      window.removeEventListener('beforeprint', onBeforePrint)
      window.removeEventListener('afterprint', onAfterPrint)
    }
  }, [])

  function toggleChart(id: string) {
    setEnabled(prev =>
      prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id],
    )
  }

  function removeChart(id: string) {
    setEnabled(prev => prev.filter(c => c !== id))
  }

  function handlePrint() {
    // beforeprint/afterprint handlers (registered in useEffect above)
    // set explicit SVG dimensions at the right moment — just call print directly.
    window.print()
  }

  if (!project) {
    return (
      <EmptyState
        icon={<TrendingUp className="h-10 w-10" />}
        title="No project selected"
        description="Select a project from the top bar to view trend data"
      />
    )
  }

  const trendData = trends ?? []

  const totalPassed  = trendData.reduce((s: number, d: TrendPoint) => s + d.passed,  0)
  const totalFailed  = trendData.reduce((s: number, d: TrendPoint) => s + d.failed,  0)
  const totalSkipped = trendData.reduce((s: number, d: TrendPoint) => s + d.skipped, 0)
  const totalBroken  = trendData.reduce((s: number, d: TrendPoint) => s + d.broken,  0)
  const avgPassRate  = trendData.length > 0
    ? (trendData.reduce((s: number, d: TrendPoint) => s + d.pass_rate, 0) / trendData.length).toFixed(1)
    : '—'

  const availableToAdd = CHART_CATALOG.filter(c => !enabledCharts.includes(c.id))

  return (
    <>
      {/* Modals */}
      {showPicker && (
        <ChartPickerModal enabled={enabledCharts} onToggle={toggleChart} onClose={() => setShowPicker(false)} />
      )}
      {showEmail && projectId && (
        <EmailModal onClose={() => setShowEmail(false)} projectId={projectId} days={days} enabledCharts={enabledCharts} />
      )}

      <div className="space-y-6 print:space-y-4">
        <PageHeader
          title="Trends"
          subtitle={`Historical trends for ${project.name}`}
          actions={
            <div className="flex items-center gap-2 print:hidden">
              {/* Period selector */}
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
              {/* Customize */}
              <button
                onClick={() => setShowPicker(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition-colors"
              >
                <Settings2 className="h-3.5 w-3.5" />
                Customize
              </button>
              {/* Export PDF */}
              <button
                onClick={handlePrint}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition-colors"
              >
                <Download className="h-3.5 w-3.5" />
                Export PDF
              </button>
              {/* Email */}
              <button
                onClick={() => setShowEmail(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition-colors"
              >
                <Mail className="h-3.5 w-3.5" />
                Email Report
              </button>
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
            description="Run some tests to see trends over time"
          />
        ) : (
          <>
            <div className="space-y-4">
              {enabledCharts.map(chartId => {
                const def = CHART_CATALOG.find(c => c.id === chartId)
                if (!def) return null
                return (
                  <div key={chartId} className="card relative group">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-sm font-semibold text-slate-200">{def.label}</h3>
                      <button
                        onClick={() => removeChart(chartId)}
                        className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 transition-all print:hidden"
                        title="Remove chart"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                    {renderChart(chartId, trendData)}
                  </div>
                )
              })}
            </div>

            {/* Add chart button */}
            {availableToAdd.length > 0 && (
              <div className="print:hidden">
                <button
                  onClick={() => setShowPicker(true)}
                  className="w-full flex items-center justify-center gap-2 py-4 border-2 border-dashed border-slate-700 hover:border-slate-500 rounded-xl text-slate-500 hover:text-slate-300 transition-colors text-sm font-medium"
                >
                  <Plus className="h-4 w-4" />
                  Add Chart ({availableToAdd.length} available)
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Print styles
          Key design: apply print-color-adjust:exact ONLY to SVG elements so that
          Recharts chart colours (bar fills, line strokes) are preserved.
          ALL HTML element backgrounds are forced to white so dark Tailwind
          utility classes (bg-slate-800/900) do NOT produce a black page.
      */}
      <style>{`
        @media print {
          /* ── Page defaults ── */
          @page { margin: 15mm; }
          html, body {
            background: white !important;
            color: #1e293b !important;
            margin: 0;
          }

          /* ── Force white background on every HTML element ── */
          div, section, article, main, header, aside,
          span, p, h1, h2, h3, h4, h5, h6,
          table, thead, tbody, tr, td, th, ul, li, button, select, input {
            background: white !important;
            background-color: white !important;
            color: #1e293b !important;
            border-color: #e2e8f0 !important;
            box-shadow: none !important;
          }

          /* ── Hide chrome / controls ── */
          .print\\:hidden { display: none !important; }
          nav, aside, [data-sidebar], [data-topbar] { display: none !important; }
          .recharts-tooltip-wrapper { display: none !important; }

          /* ── Layout ── */
          main { margin: 0 !important; padding: 0 !important; width: 100% !important; max-width: none !important; }
          .grid { display: grid !important; }

          /* ── Cards ── */
          .card {
            border: 1px solid #cbd5e1 !important;
            margin-bottom: 16px !important;
            break-inside: avoid !important;
            page-break-inside: avoid !important;
            padding: 12px !important;
          }

          /* ── Headings ── */
          h1, h2, h3 { color: #0f172a !important; font-weight: 700; }

          /* ── SVGs: preserve chart data colours ── */
          svg {
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
            overflow: visible !important;
          }

          /* ── Recharts axis text → dark so it's readable on white ── */
          .recharts-text tspan,
          .recharts-cartesian-axis-tick-value tspan {
            fill: #475569 !important;
          }

          /* ── Grid lines → light grey on white background ── */
          .recharts-cartesian-grid-horizontal line,
          .recharts-cartesian-grid-vertical line {
            stroke: #e2e8f0 !important;
          }

          /* ── Axis lines ── */
          .recharts-cartesian-axis-line { stroke: #94a3b8 !important; }

          /* ── Legend text ── */
          .recharts-legend-item-text { color: #475569 !important; fill: #475569 !important; }

          /* ── Recharts sizing: lock to explicit px so ResizeObserver cannot
             collapse the SVG to 0 when @media print reflows the page ── */
          .recharts-responsive-container {
            width: 680px !important;
            min-width: 680px !important;
            overflow: visible !important;
          }
          .recharts-wrapper {
            width: 680px !important;
            overflow: visible !important;
          }
          .recharts-surface {
            width: 680px !important;
            overflow: visible !important;
          }

          /* ── Print title at top of first page ── */
          body::before {
            content: "QA Insight — Trends Report";
            display: block;
            font-size: 20px;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 12px;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 8px;
          }
        }
      `}</style>
    </>
  )
}
