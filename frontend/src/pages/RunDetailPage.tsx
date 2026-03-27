import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ChevronRight, Package, PencilLine, X, Check } from 'lucide-react'
import PageHeader from '@/components/ui/PageHeader'
import StatusBadge from '@/components/ui/StatusBadge'
import Pagination from '@/components/ui/Pagination'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useRun, useTestCases } from '@/hooks/useRuns'
import { formatDateTime, formatDuration } from '@/utils/formatters'
import { clsx } from 'clsx'
import { runsService } from '@/services/runsService'
import { mutate } from 'swr'

interface TestCase {
  id: string
  test_name: string
  class_name?: string
  suite_name?: string
  status: string
  duration_ms?: number
  failure_category?: string
}

const STATUSES = ['', 'FAILED', 'BROKEN', 'PASSED', 'SKIPPED']

function ReleaseTag({ releaseName, onSet }: {
  releaseName?: string
  onSet: (name: string) => Promise<void>
}) {
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    const name = value.trim()
    if (!name) return
    setSaving(true)
    try {
      await onSet(name)
      setEditing(false)
      setValue('')
    } finally {
      setSaving(false)
    }
  }

  if (editing) {
    return (
      <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
        <input
          autoFocus
          type="text"
          placeholder="Release name (e.g. v2.5.0)"
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setEditing(false) }}
          className="bg-slate-700 border border-slate-600 rounded px-2 py-0.5 text-xs text-slate-200 placeholder-slate-500 w-44 focus:outline-none focus:border-blue-500"
        />
        <button onClick={handleSave} disabled={saving} className="text-emerald-400 hover:text-emerald-300 disabled:opacity-50">
          <Check className="h-4 w-4" />
        </button>
        <button onClick={() => setEditing(false)} className="text-slate-500 hover:text-slate-300">
          <X className="h-4 w-4" />
        </button>
      </div>
    )
  }

  if (releaseName) {
    return (
      <div className="flex items-center gap-2">
        <button
          onClick={() => navigate('/releases')}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-violet-900/40 text-violet-300 hover:bg-violet-800/50 transition-colors"
        >
          <Package className="h-3 w-3" />
          {releaseName}
        </button>
        <button onClick={() => setEditing(true)} title="Change release" className="text-slate-600 hover:text-slate-400">
          <PencilLine className="h-3.5 w-3.5" />
        </button>
      </div>
    )
  }

  return (
    <button
      onClick={() => setEditing(true)}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border border-dashed border-slate-600 text-slate-500 hover:text-slate-300 hover:border-slate-400 transition-colors"
    >
      <Package className="h-3 w-3" />
      Set release
    </button>
  )
}

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

  async function handleSetRelease(name: string) {
    if (!runId) return
    await runsService.setRelease(runId, name)
    mutate(['run', runId])
  }

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
            <div className="flex items-center gap-3 text-sm flex-wrap">
              <ReleaseTag
                releaseName={run.release_name}
                onSet={handleSetRelease}
              />
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
                {((data?.items ?? []) as TestCase[]).map((tc) => (
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
