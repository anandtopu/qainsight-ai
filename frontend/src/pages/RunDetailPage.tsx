import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ChevronRight } from 'lucide-react'
import PageHeader from '@/components/ui/PageHeader'
import StatusBadge from '@/components/ui/StatusBadge'
import Pagination from '@/components/ui/Pagination'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useRun, useTestCases } from '@/hooks/useRuns'
import { formatDateTime, formatDuration } from '@/utils/formatters'
import { clsx } from 'clsx'

const STATUSES = ['', 'FAILED', 'BROKEN', 'PASSED', 'SKIPPED']

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [suiteFilter, setSuiteFilter] = useState('')

  const { data: run } = useRun(runId)
  const { data, isLoading } = useTestCases(runId, {
    page, size: 50,
    ...(statusFilter && { status: statusFilter }),
    ...(suiteFilter && { suite: suiteFilter }),
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-2">
        <button onClick={() => navigate('/runs')} className="hover:text-slate-200 flex items-center gap-1">
          <ArrowLeft className="h-4 w-4" /> Runs
        </button>
        <ChevronRight className="h-3 w-3" />
        <span className="text-slate-200 font-mono">#{run?.build_number ?? '…'}</span>
      </div>

      {run && (
        <PageHeader
          title={`Run #${run.build_number}`}
          subtitle={`${run.jenkins_job ?? 'Jenkins'} · ${formatDateTime(run.created_at)}`}
          actions={
            <div className="flex items-center gap-3 text-sm">
              <span className="text-emerald-400 font-medium">{run.passed_tests} passed</span>
              <span className="text-red-400 font-medium">{run.failed_tests} failed</span>
              <span className="text-amber-400 font-medium">{run.skipped_tests} skipped</span>
              <span className="text-slate-500">/ {run.total_tests} total</span>
              <StatusBadge status={run.status} />
            </div>
          }
        />
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
          {STATUSES.map(s => (
            <button
              key={s || 'all'}
              onClick={() => { setStatusFilter(s); setPage(1) }}
              className={clsx(
                'px-3 py-1 rounded-md text-sm font-medium transition-colors',
                statusFilter === s ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-100',
              )}
            >
              {s || 'All'}
            </button>
          ))}
        </div>
        <input
          type="text"
          placeholder="Filter by suite…"
          className="input w-48 h-9"
          value={suiteFilter}
          onChange={e => { setSuiteFilter(e.target.value); setPage(1) }}
        />
      </div>

      {/* Test case table */}
      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-20"><LoadingSpinner size="lg" /></div>
        ) : (
          <>
            <table className="w-full">
              <thead className="border-b border-slate-800">
                <tr>
                  {['Test Name', 'Suite', 'Status', 'Duration', 'Category', ''].map(h => (
                    <th key={h} className="th">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(data?.items ?? []).map((tc: any) => (
                  <tr
                    key={tc.id}
                    className="table-row"
                    onClick={() => navigate(`/runs/${runId}/tests/${tc.id}`)}
                  >
                    <td className="td max-w-[280px]">
                      <p className="truncate text-slate-200 text-sm font-medium">{tc.test_name}</p>
                      {tc.class_name && <p className="truncate text-xs text-slate-500 font-mono mt-0.5">{tc.class_name}</p>}
                    </td>
                    <td className="td text-slate-400 text-sm truncate max-w-[160px]">{tc.suite_name ?? '—'}</td>
                    <td className="td"><StatusBadge status={tc.status} /></td>
                    <td className="td text-slate-400">{formatDuration(tc.duration_ms)}</td>
                    <td className="td">
                      {tc.failure_category && (
                        <span className="text-xs text-slate-400">{tc.failure_category.replace('_', ' ')}</span>
                      )}
                    </td>
                    <td className="td text-slate-600">
                      <ChevronRight className="h-4 w-4" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data && <Pagination page={page} pages={data.pages} total={data.total} onChange={setPage} />}
          </>
        )}
      </div>
    </div>
  )
}
