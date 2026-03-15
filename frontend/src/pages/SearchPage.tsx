import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Search } from 'lucide-react'
import PageHeader from '@/components/ui/PageHeader'
import StatusBadge from '@/components/ui/StatusBadge'
import Pagination from '@/components/ui/Pagination'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { searchService } from '@/services/searchService'
import { fromNow } from '@/utils/formatters'
import { useProjectStore } from '@/store/projectStore'

export default function SearchPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const projectId = useProjectStore(s => s.activeProjectId)
  const [query, setQuery] = useState(searchParams.get('q') ?? '')
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [results, setResults] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)

  const doSearch = async (q: string, p = 1) => {
    if (!q.trim()) return
    setLoading(true)
    try {
      const data = await searchService.search({ q, project_id: projectId ?? undefined, page: p, size: 25 })
      setResults(data)
      setPage(p)
    } finally {
      setLoading(false)
    }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (query) doSearch(query) }, [])

  return (
    <div className="space-y-4">
      <PageHeader title="Search" subtitle="Full-text search across all test cases and history" />

      {/* Search bar */}
      <div className="flex gap-3">
        <div className="relative flex-1 max-w-2xl">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <input
            type="text"
            className="input pl-9 h-11 text-base"
            placeholder="Search test names, error messages, suites…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && doSearch(query)}
            autoFocus
          />
        </div>
        <button className="btn-primary px-6" onClick={() => doSearch(query)} disabled={loading}>
          {loading ? <LoadingSpinner size="sm" /> : 'Search'}
        </button>
      </div>

      {/* Results */}
      {results && (
        <div className="space-y-2">
          <p className="text-sm text-slate-400">
            {results.total} results for <span className="text-slate-200 font-medium">"{results.query}"</span>
          </p>
          <div className="card p-0 overflow-hidden">
            <table className="w-full">
              <thead className="border-b border-slate-800">
                <tr>
                  {['Test Name', 'Suite', 'Status', 'Failures', 'Last Run'].map(h => (
                    <th key={h} className="th">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                {results.items.map((r: any) => (
                  <tr
                    key={r.test_case_id}
                    className="table-row"
                    onClick={() => navigate(`/runs/${r.test_run_id}/tests/${r.test_case_id}`)}
                  >
                    <td className="td">
                      <p className="text-slate-200 text-sm font-medium truncate max-w-[260px]">{r.test_name}</p>
                    </td>
                    <td className="td text-slate-400 text-sm truncate max-w-[140px]">{r.suite_name ?? '—'}</td>
                    <td className="td"><StatusBadge status={r.status} /></td>
                    <td className="td text-red-400 font-medium">{r.failure_count}</td>
                    <td className="td text-slate-400 text-sm">{fromNow(r.last_run_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination page={page} pages={results.pages} total={results.total}
              onChange={p => doSearch(query, p)} />
          </div>
        </div>
      )}

      {!results && !loading && (
        <div className="flex flex-col items-center justify-center py-20 text-slate-500">
          <Search className="h-12 w-12 mb-3 text-slate-700" />
          <p>Enter a search term and press Enter</p>
        </div>
      )}
    </div>
  )
}
