import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GitBranch } from 'lucide-react'
import PageHeader from '@/components/ui/PageHeader'
import StatusBadge from '@/components/ui/StatusBadge'
import Pagination from '@/components/ui/Pagination'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import EmptyState from '@/components/ui/EmptyState'
import { useRuns } from '@/hooks/useRuns'
import { formatDateTime, fromNow, formatDuration, formatPassRate } from '@/utils/formatters'
import { useProjectStore } from '@/store/projectStore'

export default function RunsPage() {
  const navigate = useNavigate()
  const project = useProjectStore(s => s.activeProject)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')

  const { data, isLoading } = useRuns({ page, size: 20, ...(statusFilter && { status: statusFilter }) })

  if (!project) {
    return (
      <EmptyState
        icon={<GitBranch className="h-10 w-10" />}
        title="No project selected"
        description="Select a project from the top bar to view test runs"
      />
    )
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Test Runs"
        subtitle={`Jenkins builds for ${project.name}`}
        actions={
          <select
            className="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={statusFilter}
            onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
          >
            <option value="">All statuses</option>
            <option value="FAILED">Failed</option>
            <option value="PASSED">Passed</option>
            <option value="IN_PROGRESS">In Progress</option>
          </select>
        }
      />

      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-20"><LoadingSpinner size="lg" /></div>
        ) : !data?.items?.length ? (
          <EmptyState
            icon={<GitBranch className="h-8 w-8" />}
            title="No runs found"
            description="Test results will appear here after your first Jenkins build"
          />
        ) : (
          <>
            <table className="w-full">
              <thead className="border-b border-slate-800">
                <tr>
                  {['Build', 'Job', 'Branch', 'Status', 'Tests', 'Pass Rate', 'Duration', 'Started', ''].map(h => (
                    <th key={h} className="th">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                {data.items.map((run: any) => (
                  <tr
                    key={run.id}
                    className="table-row"
                    onClick={() => navigate(`/runs/${run.id}`)}
                  >
                    <td className="td font-mono text-blue-400 font-medium">#{run.build_number}</td>
                    <td className="td text-slate-400 truncate max-w-[160px]">{run.jenkins_job ?? '—'}</td>
                    <td className="td text-slate-400">{run.branch ?? '—'}</td>
                    <td className="td"><StatusBadge status={run.status} /></td>
                    <td className="td">
                      <span className="text-emerald-400">{run.passed_tests}</span>
                      <span className="text-slate-600 mx-1">/</span>
                      <span className="text-red-400">{run.failed_tests}</span>
                      <span className="text-slate-600 mx-1">/</span>
                      <span className="text-slate-400">{run.total_tests}</span>
                    </td>
                    <td className="td font-medium">{formatPassRate(run.pass_rate)}</td>
                    <td className="td text-slate-400">{formatDuration(run.duration_ms)}</td>
                    <td className="td text-slate-400" title={formatDateTime(run.created_at)}>{fromNow(run.created_at)}</td>
                    <td className="td text-slate-600 text-xs">{run.ocp_pod_name ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination page={page} pages={data.pages} total={data.total} onChange={setPage} />
          </>
        )}
      </div>
    </div>
  )
}
